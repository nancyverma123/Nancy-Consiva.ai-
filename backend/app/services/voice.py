"""Voice services: ElevenLabs text-to-speech (streamed + cached) and Groq Whisper speech-to-text."""

import hashlib
import logging
import os
import re
import tempfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import VoiceUsage
from app.services.llm_client import get_client

logger = logging.getLogger("consiva.voice")
settings = get_settings()

_BACKEND_DIR = Path(__file__).resolve().parents[2]

# Whisper's verbose_json returns full language names; the rest of the app uses ISO codes.
WHISPER_LANGUAGE_CODES = {
    "english": "en", "hindi": "hi", "arabic": "ar", "spanish": "es", "french": "fr",
    "german": "de", "portuguese": "pt", "chinese": "zh-cn", "japanese": "ja", "bengali": "bn",
    "tamil": "ta", "telugu": "te", "marathi": "mr", "gujarati": "gu", "urdu": "ur",
}

# Phrases Whisper commonly invents from silence or background noise.
_WHISPER_HALLUCINATIONS = {
    "thank you.", "thank you", "thanks for watching.", "thanks for watching!", "you",
    "bye.", "subtitles by the amara.org community", ".", "",
}


STT_VOCABULARY_PROMPT = "Consiva, Consiva.ai, DPDP, DPDP Act, ROPA, CERT-In, DPA, CMP, consent management, data breach."


class VoiceUnavailableError(Exception):
    """TTS provider is misconfigured, out of credits, or temporarily failing."""


class VoiceQuotaExceededError(Exception):
    """A per-user or global daily character limit would be exceeded."""


# ---------- Text preparation ----------

def prepare_speech_text(text: str) -> str:
    """Turn a chat answer (possibly markdown) into clean text that sounds natural when read aloud."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url) -> label
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"【[^】]*】", "", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", text, flags=re.M)
    text = re.sub(r"[*_`~|>]+", "", text)
    text = re.sub(r"\s*\n+\s*", ". ", text)
    text = re.sub(r"\.(\s*\.)+", ".", text)
    text = re.sub(r"([:;!?])\.", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" .")
    if text and text[-1] not in ".!?।؟":
        text += "."
    return _truncate_at_sentence(text, settings.tts_max_chars_per_request)


def _truncate_at_sentence(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    boundary = max(cut.rfind(p) for p in (". ", "! ", "? ", "। ", "؟ "))
    return cut[: boundary + 1] if boundary > limit * 0.5 else cut.rsplit(" ", 1)[0] + "."


def _tts_language_code(language: str | None) -> str | None:
    if not language:
        return None
    return language.lower().split("-")[0]  # "zh-cn" -> "zh"


def _voice_for(language: str | None) -> str:
    code = _tts_language_code(language)
    return settings.elevenlabs_voice_overrides_map.get(code or "", settings.elevenlabs_voice_id)


# ---------- Quota ----------

def _reserve_characters(db: Session, user_id: str, count: int) -> None:
    today = date.today()
    global_used = (
        db.query(func.coalesce(func.sum(VoiceUsage.characters), 0)).filter(VoiceUsage.day == today).scalar()
    )
    usage = db.query(VoiceUsage).filter(VoiceUsage.user_id == user_id, VoiceUsage.day == today).first()
    user_used = usage.characters if usage else 0

    if user_used + count > settings.tts_daily_chars_per_user or global_used + count > settings.tts_daily_chars_global:
        raise VoiceQuotaExceededError

    if usage is None:
        usage = VoiceUsage(user_id=user_id, day=today, characters=0)
        db.add(usage)
    usage.characters = user_used + count
    db.commit()


def _release_characters(db: Session, user_id: str, count: int) -> None:
    """Refund a reservation when ElevenLabs didn't produce audio."""
    usage = db.query(VoiceUsage).filter(VoiceUsage.user_id == user_id, VoiceUsage.day == date.today()).first()
    if usage is not None:
        usage.characters = max(usage.characters - count, 0)
        db.commit()


def get_usage(db: Session, user_id: str) -> tuple[int, int]:
    """Characters used today as (this user, everyone)."""
    today = date.today()
    global_used = (
        db.query(func.coalesce(func.sum(VoiceUsage.characters), 0)).filter(VoiceUsage.day == today).scalar()
    )
    usage = db.query(VoiceUsage).filter(VoiceUsage.user_id == user_id, VoiceUsage.day == today).first()
    return (usage.characters if usage else 0), int(global_used)


def reset_today_usage(db: Session) -> None:
    """Development only: clear today's counters for all users."""
    db.query(VoiceUsage).filter(VoiceUsage.day == date.today()).delete()
    db.commit()


# ---------- Text-to-speech ----------

def _cache_path(voice_id: str, language: str | None, text: str) -> Path:
    key = f"{settings.elevenlabs_model_id}|{settings.elevenlabs_output_format}|{voice_id}|{language}|{text}"
    cache_dir = Path(settings.voice_cache_dir)
    if not cache_dir.is_absolute():
        cache_dir = _BACKEND_DIR / cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.mp3"


def _iter_file(path: Path) -> Iterator[bytes]:
    with open(path, "rb") as f:
        while chunk := f.read(16_384):
            yield chunk


def synthesize_speech_stream(db: Session, user_id: str, text: str, language: str | None) -> Iterator[bytes]:
    """Return an iterator of MP3 bytes. Checks cache and quota *before* returning, so HTTP errors
    can still be reported with a proper status code rather than mid-stream."""
    if not settings.elevenlabs_api_key:
        raise VoiceUnavailableError("ElevenLabs API key is not configured")

    speech_text = prepare_speech_text(text)
    if not speech_text:
        raise ValueError("Nothing to speak")

    voice_id = _voice_for(language)
    language_code = _tts_language_code(language)
    cache_file = _cache_path(voice_id, language_code, speech_text)
    if cache_file.exists():
        return _iter_file(cache_file)

    _reserve_characters(db, user_id, len(speech_text))

    body = {"text": speech_text, "model_id": settings.elevenlabs_model_id}
    if language_code:
        body["language_code"] = language_code

    client = httpx.Client(base_url=settings.elevenlabs_base_url, timeout=httpx.Timeout(30.0, connect=10.0))
    request = client.build_request(
        "POST",
        f"/v1/text-to-speech/{voice_id}/stream",
        params={"output_format": settings.elevenlabs_output_format},
        headers={"xi-api-key": settings.elevenlabs_api_key, "Accept": "audio/mpeg"},
        json=body,
    )
    try:
        response = client.send(request, stream=True)
    except httpx.HTTPError as exc:
        client.close()
        _release_characters(db, user_id, len(speech_text))
        raise VoiceUnavailableError(f"ElevenLabs request failed: {exc}") from exc

    if response.status_code != 200:
        detail = response.read()[:500]
        response.close()
        client.close()
        _release_characters(db, user_id, len(speech_text))
        logger.error("ElevenLabs TTS error %s: %s", response.status_code, detail)
        raise VoiceUnavailableError(f"ElevenLabs returned {response.status_code}")

    return _stream_and_cache(client, response, cache_file)


def _stream_and_cache(client: httpx.Client, response: httpx.Response, cache_file: Path) -> Iterator[bytes]:
    # Write to a temp file while streaming; only promote it into the cache if the stream completes.
    fd, tmp_name = tempfile.mkstemp(dir=cache_file.parent, suffix=".part")
    completed = False
    try:
        with os.fdopen(fd, "wb") as tmp:
            for chunk in response.iter_bytes():
                tmp.write(chunk)
                yield chunk
        completed = True
    except httpx.HTTPError:
        logger.exception("ElevenLabs stream interrupted")
    finally:
        response.close()
        client.close()
        if completed:
            os.replace(tmp_name, cache_file)
        elif os.path.exists(tmp_name):
            os.remove(tmp_name)


# ---------- Speech-to-text ----------

def transcribe_audio(audio: bytes, filename: str, language: str | None) -> tuple[str, str | None]:
    """Transcribe with Groq Whisper. Returns (text, detected ISO language code)."""
    kwargs = {}
    if language:
        kwargs["language"] = language.split("-")[0]

    result = get_client().audio.transcriptions.create(
        model=settings.groq_stt_model,
        file=(filename, audio),
        response_format="verbose_json",
        temperature=0.0,
        # Vocabulary hint so brand and compliance terms are spelled correctly.
        prompt=STT_VOCABULARY_PROMPT,
        **kwargs,
    )

    segments = getattr(result, "segments", None) or []
    # Drop segments Whisper itself flags as probably-not-speech (noise, breathing, echo).
    kept = [
        s for s in segments
        if not (_seg(s, "no_speech_prob", 0.0) > 0.6 and _seg(s, "avg_logprob", 0.0) < -0.7)
    ]
    text = " ".join(_seg(s, "text", "").strip() for s in kept).strip() if segments else (result.text or "").strip()

    if text.lower() in _WHISPER_HALLUCINATIONS:
        text = ""

    detected = WHISPER_LANGUAGE_CODES.get((getattr(result, "language", "") or "").lower())
    return text, detected


def _seg(segment, key: str, default):
    return segment.get(key, default) if isinstance(segment, dict) else getattr(segment, key, default)
