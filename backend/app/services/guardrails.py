"""Guardrails: layered prompt-injection and abuse protection for the chat pipeline.

Layers (each one assumes the others can fail):
1. Input  - normalise text, catch obvious injection patterns, and score with Llama Prompt Guard 2.
2. Prompt - retrieved content and the user's question are wrapped in per-request random tags so
            injected text can't "close" a block, and the system prompt carries a secret canary.
3. Output - block replies that leak the system prompt, and strip links, emails and phone numbers
            that don't appear in the retrieved Consiva content (stops injected phishing details).
"""

import logging
import re
import secrets
import unicodedata
from dataclasses import dataclass

from openai import APIError

from app.config import get_settings
from app.services.llm_client import get_client

logger = logging.getLogger("consiva.guardrails")
settings = get_settings()

BLOCKED_INPUT_REPLY = (
    "I can't help with that request. I'm here to answer questions about DPDP compliance, data "
    "privacy, and how Consiva can help your team. What would you like to know?"
)

BLOCKED_OUTPUT_REPLY = (
    "Sorry, I can't share that. I'm happy to help with questions about DPDP compliance, data "
    "privacy, or Consiva's platform."
)

# A per-process secret placed in the system prompt. If it ever shows up in a reply, the model is
# leaking its instructions.
SYSTEM_PROMPT_CANARY = f"cnv-{secrets.token_hex(8)}"

# Headings that only exist in the system prompt; quoting them verbatim means a leak.
_SYSTEM_PROMPT_FINGERPRINTS = (
    "FALLBACK RULES",
    "ACCURACY AND ANTI-HALLUCINATION RULES",
    "RETRIEVED CONTEXT RULE",
    "SECURITY RULES",
    "[OUT_OF_SCOPE]",
    "[NO_CONTEXT]",
)

# Invisible or formatting characters used to smuggle hidden instructions past filters.
_INVISIBLE_CHARS = re.compile(r"[​-‏‪-‮⁠-⁤⁦-⁩﻿­]")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Chat-template and role tokens that have no place in a customer question.
_ROLE_TOKENS = re.compile(
    r"<\|?(?:im_start|im_end|system|endoftext|eot_id|start_header_id|end_header_id)\|?>"
    r"|\[/?INST\]|<</?SYS>>|^\s*#{2,}\s*(?:system|instruction)s?\b",
    re.IGNORECASE | re.MULTILINE,
)

# High-precision English patterns. The multilingual classifier covers everything else.
_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:ignore|disregard|forget|override|bypass)\b.{0,40}\b(?:previous|prior|above|earlier|all|your|the|system)\b.{0,30}\b(?:instructions?|prompts?|rules?|guidelines?|directives?|context)\b",
        r"\b(?:reveal|show|print|repeat|output|display|leak|tell me)\b.{0,40}\b(?:system|hidden|initial|original|developer)\s+(?:prompt|instructions?|message|rules)\b",
        r"\b(?:you are now|from now on,? you are|act as|pretend to be|roleplay as)\b.{0,60}\b(?:dan|jailbroken|unrestricted|unfiltered|without (?:any )?(?:rules|restrictions|limits))\b",
        r"\b(?:developer|debug|god|sudo|admin)\s+mode\b",
        r"\bdo anything now\b",
        r"\bnew (?:system )?instructions?\s*:",
    )
]


@dataclass
class InputCheck:
    text: str  # normalised text to use downstream
    blocked: bool
    reason: str | None = None
    score: float = 0.0


def normalize_user_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE_CHARS.sub("", text)
    text = _CONTROL_CHARS.sub("", text)
    return text.strip()


def _heuristic_reason(text: str) -> str | None:
    if _ROLE_TOKENS.search(text):
        return "role_token"
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return "injection_pattern"
    return None


def _prompt_guard_score(text: str) -> float | None:
    """Max injection probability across windows (the classifier reads ~512 tokens at a time).
    Returns None if the classifier is unavailable, so the caller can fail open to heuristics."""
    windows = [text[i : i + 1500] for i in range(0, len(text), 1200)] or [text]
    best = 0.0
    try:
        for window in windows[:4]:
            result = get_client().chat.completions.create(
                model=settings.prompt_guard_model,
                messages=[{"role": "user", "content": window}],
                timeout=5,
            )
            best = max(best, float((result.choices[0].message.content or "0").strip()))
    except (APIError, ValueError) as exc:
        logger.warning("Prompt Guard unavailable, using heuristics only: %s", exc)
        return None
    return best


def check_user_input(text: str, user_id: str) -> InputCheck:
    clean = normalize_user_text(text)
    if not clean:
        return InputCheck(text=clean, blocked=True, reason="empty")

    reason = _heuristic_reason(clean)
    if reason:
        log_security_event("input_blocked", user_id, reason=reason, sample=clean)
        return InputCheck(text=clean, blocked=True, reason=reason, score=1.0)

    if settings.prompt_guard_enabled:
        score = _prompt_guard_score(clean)
        if score is not None and score >= settings.prompt_guard_block_threshold:
            log_security_event("input_blocked", user_id, reason="prompt_guard", score=score, sample=clean)
            return InputCheck(text=clean, blocked=True, reason="prompt_guard", score=score)
        return InputCheck(text=clean, blocked=False, score=score or 0.0)

    return InputCheck(text=clean, blocked=False)


# ---------- Prompt construction ----------

def new_boundary() -> str:
    """Random tag name for this request; injected text can't guess it to break out of a block."""
    return f"data-{secrets.token_hex(6)}"


def neutralize_boundaries(text: str) -> str:
    """Defang anything in untrusted text that looks like our wrapper tags."""
    return re.sub(r"</?\s*data-[0-9a-f]{6,}\s*>", "[removed]", text, flags=re.IGNORECASE)


# ---------- Output checks ----------

_URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>()\"']+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|ai|in|io|net|org|co|app|dev|xyz|link|ly)(?:/[^\s<>()\"']*)?", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{8,}\d)(?!\w)")


def _domain(url: str) -> str:
    host = re.sub(r"^(?:https?://)?(?:www\.)?", "", url.lower()).split("/")[0]
    return host.rstrip(".,;:")


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def check_model_output(answer: str, context_text: str, user_id: str) -> str:
    """Return a safe version of the model's answer."""
    if SYSTEM_PROMPT_CANARY in answer or sum(f in answer for f in _SYSTEM_PROMPT_FINGERPRINTS) >= 2:
        log_security_event("output_blocked", user_id, reason="system_prompt_leak", sample=answer)
        return BLOCKED_OUTPUT_REPLY

    context_lower = context_text.lower()
    allowed_domains = {d.strip().lower() for d in settings.guard_allowed_link_domains.split(",") if d.strip()}
    context_digits = _digits(context_text)
    removed: list[str] = []

    def replace_email(match: re.Match) -> str:
        if match.group(0).lower() in context_lower:
            return match.group(0)
        removed.append("email")
        return "[contact details removed]"

    def replace_url(match: re.Match) -> str:
        url = match.group(0).rstrip(".,;:)")
        trailing = match.group(0)[len(url):]
        domain = _domain(url)
        if (
            domain in context_lower
            or domain in allowed_domains
            or any(domain.endswith("." + d) for d in allowed_domains)
        ):
            return match.group(0)
        removed.append("url")
        return "[link removed]" + trailing

    def replace_phone(match: re.Match) -> str:
        digits = _digits(match.group(0))
        # Years, section numbers and similar short numbers aren't phone numbers.
        if len(digits) < 10 or digits in context_digits:
            return match.group(0)
        removed.append("phone")
        return "[number removed]"

    safe = _EMAIL_RE.sub(replace_email, answer)
    safe = _URL_RE.sub(replace_url, safe)
    safe = _PHONE_RE.sub(replace_phone, safe)

    if removed:
        log_security_event("output_sanitized", user_id, reason=",".join(sorted(set(removed))), sample=answer)
    return safe


# ---------- Logging ----------

def log_security_event(event: str, user_id: str, reason: str | None = None, score: float | None = None, sample: str = "") -> None:
    # Truncated sample only: enough to investigate, without storing whole conversations in logs.
    logger.warning(
        "security_event=%s user=%s reason=%s score=%s sample=%r",
        event,
        user_id,
        reason,
        f"{score:.3f}" if score is not None else "-",
        sample[:160],
    )
