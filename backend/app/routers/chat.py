import logging
import traceback

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from openai import APIError, APITimeoutError

from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Conversation, Message, User
from app.schemas import ChatRequest, ChatResponse, SourceCitation
from app.services.guardrails import BLOCKED_INPUT_REPLY, check_user_input
from app.services.language import LANGUAGE_NAMES, detect_language
from app.services.rate_limit import enforce_chat
from app.services.rag import generate_answer


logger = logging.getLogger("consiva.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])


HUMAN_FRIENDLY_ERROR = (
    "Sorry, I hit a snag answering that. Please try again in a moment."
)


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enforce_chat(user.id)

    guard = check_user_input(payload.message, user.id)
    message_text = guard.text or payload.message

    # The language code is inserted into the system prompt,
    # so only accept known codes.
    requested = (payload.language or "").strip().lower()

    language = (
        requested
        if requested in LANGUAGE_NAMES
        else detect_language(message_text)
    )

    conversation = None

    if payload.conversation_id:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == user.id,
            )
            .first()
        )

        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

    if conversation is None:
        conversation = Conversation(
            user_id=user.id,
            title=message_text[:60],
            language=language,
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    history = _safe_history(conversation.messages[-10:])

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=message_text,
        language=language,
    )

    db.add(user_message)
    db.commit()

    if guard.blocked:
        return _save_reply(
            db,
            conversation,
            BLOCKED_INPUT_REPLY,
            [],
            language,
            grounded=False,
        )

    try:
        logger.info(
            "Starting generate_answer | user_id=%s | conversation_id=%s | message=%s",
            user.id,
            conversation.id,
            message_text[:100],
        )

        answer, chunks, grounded = generate_answer(
            message_text,
            history,
            language,
            voice_mode=payload.voice_mode,
            user_id=user.id,
        )

        logger.info(
            "generate_answer completed | chunks=%s | grounded=%s",
            len(chunks),
            grounded,
        )

    except (APIError, APITimeoutError) as exc:
        logger.exception(
            "LLM/Pinecone API error | type=%s | error=%s",
            type(exc).__name__,
            str(exc),
        )

        error_trace = traceback.format_exc()

        print("========== LLM/PINECONE ERROR ==========")
        print(error_trace)
        print("=========================================")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": error_trace,
            },
        ) from exc

    except Exception as exc:
        logger.exception(
            "UNEXPECTED CHAT ERROR | type=%s | error=%s",
            type(exc).__name__,
            str(exc),
        )

        error_trace = traceback.format_exc()

        print("========== FULL CHAT TRACEBACK ==========")
        print(error_trace)
        print("=========================================")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": error_trace,
            },
        ) from exc

    sources = [
        SourceCitation(
            document_name=c.document_name,
            section_title=c.section_title,
            page_number=c.page_number,
            source_url=c.source_url,
            score=round(c.score, 4),
        )
        for c in chunks
    ]

    return _save_reply(
        db,
        conversation,
        answer,
        sources,
        language,
        grounded=grounded,
    )


def _safe_history(messages: list[Message]) -> list[dict]:
    """
    Recent turns for the model, skipping exchanges the input guard blocked,
    so a blocked injection attempt isn't replayed into later prompts.
    """

    history: list[dict] = []

    for index, message in enumerate(messages):
        if message.role not in ("user", "assistant"):
            continue

        if message.content == BLOCKED_INPUT_REPLY:
            continue

        following = (
            messages[index + 1]
            if index + 1 < len(messages)
            else None
        )

        if (
            message.role == "user"
            and following is not None
            and following.content == BLOCKED_INPUT_REPLY
        ):
            continue

        history.append(
            {
                "role": message.role,
                "content": message.content,
            }
        )

    return history[-8:]


def _save_reply(
    db: Session,
    conversation: Conversation,
    answer: str,
    sources: list[SourceCitation],
    language: str,
    grounded: bool,
) -> ChatResponse:

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        sources=[s.model_dump() for s in sources],
        language=language,
    )

    db.add(assistant_message)

    # Adding messages doesn't touch the conversation row,
    # so bump updated_at explicitly to keep the history sidebar
    # ordered by latest activity.
    conversation.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(assistant_message)

    return ChatResponse(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        answer=answer,
        sources=sources,
        language=language,
        grounded=grounded,
    )