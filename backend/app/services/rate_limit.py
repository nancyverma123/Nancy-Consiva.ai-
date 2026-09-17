"""In-memory sliding-window rate limiter.

Good for a single backend process. When running several workers or servers, move the counters
to a shared store such as Redis so limits apply across all of them.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

from app.config import get_settings

settings = get_settings()

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def _allow(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    now = time.monotonic()
    with _lock:
        hits = _hits[key]
        while hits and now - hits[0] >= window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return False, int(window_seconds - (now - hits[0])) + 1
        hits.append(now)
        return True, 0


def enforce(key: str, limit: int, window_seconds: int, message: str) -> None:
    allowed, retry_after = _allow(key, limit, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message,
            headers={"Retry-After": str(retry_after)},
        )


def client_ip(request: Request) -> str:
    # Only trust X-Forwarded-For when explicitly running behind a known proxy.
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_chat(user_id: str) -> None:
    enforce(f"chat:min:{user_id}", settings.rate_chat_per_minute, 60,
            "You're sending messages quickly. Please wait a moment and try again.")
    enforce(f"chat:day:{user_id}", settings.rate_chat_per_day, 86_400,
            "You've reached today's message limit. Please come back tomorrow or contact our team at consiva.ai.")


def enforce_voice(user_id: str, action: str) -> None:
    enforce(f"voice:{action}:{user_id}", settings.rate_voice_per_minute, 60,
            "Voice is taking a short break. You can keep chatting by text.")


def enforce_guest_signup(ip: str) -> None:
    enforce(f"guest:{ip}", settings.rate_guest_sessions_per_hour, 3_600,
            "Too many new sessions from your network. Please try again later.")
