from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    is_guest: bool = False


# --- Chat ---

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    language: str | None = None  # BCP-47 code, e.g. "en", "hi", "ar"; auto-detected if omitted
    voice_mode: bool = False  # hands-free voice conversation: ask the model for short, speakable answers


class SourceCitation(BaseModel):
    document_name: str
    section_title: str | None = None
    page_number: int | None = None
    source_url: str | None = None
    score: float


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    sources: list[SourceCitation]
    language: str
    grounded: bool


# --- Voice ---

class SpeakRequest(BaseModel):
    # Only the assistant's own saved replies can be spoken, never arbitrary text.
    message_id: str = Field(min_length=1, max_length=36)


class TranscriptionResponse(BaseModel):
    text: str
    language: str | None = None


class VoiceConfigResponse(BaseModel):
    enabled: bool
    dev_tools: bool = False


class VoiceUsageResponse(BaseModel):
    user_characters: int
    user_limit: int
    global_characters: int
    global_limit: int


# --- History ---

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: list[dict] | None = None
    language: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: str
    title: str
    language: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]
