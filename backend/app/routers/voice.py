import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from openai import APIError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Conversation, Message, User
from app.schemas import SpeakRequest, TranscriptionResponse, VoiceConfigResponse, VoiceUsageResponse
from app.services.rate_limit import enforce_voice
from app.services.voice import (
    VoiceQuotaExceededError,
    VoiceUnavailableError,
    get_usage,
    reset_today_usage,
    synthesize_speech_stream,
    transcribe_audio,
)

logger = logging.getLogger("consiva.voice")
settings = get_settings()

router = APIRouter(prefix="/api/voice", tags=["voice"])

ALLOWED_AUDIO_TYPES = {"audio/wav", "audio/x-wav", "audio/wave", "audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4"}


@router.get("/config", response_model=VoiceConfigResponse)
def voice_config(user: User = Depends(get_current_user)):
    return VoiceConfigResponse(
        enabled=bool(settings.elevenlabs_api_key and settings.groq_api_key),
        dev_tools=_dev_tools_enabled(),
    )


def _dev_tools_enabled() -> bool:
    return settings.environment.lower() in {"development", "dev", "local"}


@router.get("/usage", response_model=VoiceUsageResponse)
def voice_usage(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user_used, global_used = get_usage(db, user.id)
    return VoiceUsageResponse(
        user_characters=user_used,
        user_limit=settings.tts_daily_chars_per_user,
        global_characters=global_used,
        global_limit=settings.tts_daily_chars_global,
    )


# TEMPORARY testing aid: resets today's voice limits. Disabled unless ENVIRONMENT=development.
@router.post("/usage/reset", response_model=VoiceUsageResponse)
def reset_voice_usage(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _dev_tools_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    reset_today_usage(db)
    return voice_usage(db, user)


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    audio: UploadFile = File(...),
    language: str | None = Form(None),
    user: User = Depends(get_current_user),
):
    enforce_voice(user.id, "transcribe")
    content_type = (audio.content_type or "").split(";")[0]
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported audio format")

    data = await audio.read(settings.stt_max_upload_bytes + 1)
    if len(data) > settings.stt_max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Recording is too long")
    if not data:
        return TranscriptionResponse(text="", language=None)

    try:
        text, detected = transcribe_audio(data, audio.filename or "speech.wav", language)
    except APIError as exc:
        logger.exception("Speech-to-text failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Voice is taking a short break. You can keep chatting by text."
        ) from exc
    return TranscriptionResponse(text=text, language=detected)


@router.post("/speak")
def speak(payload: SpeakRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    enforce_voice(user.id, "speak")
    message = (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Message.id == payload.message_id, Message.role == "assistant", Conversation.user_id == user.id)
        .first()
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    try:
        stream = synthesize_speech_stream(db, user.id, message.content, message.language)
    except VoiceQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Voice is taking a short break. You can keep chatting by text.",
        ) from exc
    except VoiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voice is taking a short break. You can keep chatting by text.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return StreamingResponse(stream, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
