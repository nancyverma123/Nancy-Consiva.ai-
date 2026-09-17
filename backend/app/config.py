from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parent.parent / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Consiva AI Chatbot"
    environment: str = "development"

    # LLM provider — Groq (OpenAI-compatible chat completions API)
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_chat_model: str = "openai/gpt-oss-120b"
    groq_reasoning_effort: str = "low"
    groq_stt_model: str = "whisper-large-v3-turbo"

    # Embeddings — local, in-process multilingual-e5-small (int8 ONNX, ~118 MB),
    # no API key or network call needed. Path is relative to the backend/ directory.
    embedding_model_dir: str = "models/multilingual-e5-small"
    embedding_model_file: str = "model_quantized.onnx"
    embedding_dimensions: int = 384

    # Voice — ElevenLabs text-to-speech. Speech-to-text uses Groq Whisper (groq_stt_model).
    elevenlabs_api_key: str = ""
    elevenlabs_base_url: str = "https://api.elevenlabs.io"
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"
    # Optional per-language voices, e.g. "hi:VOICE_ID,ar:VOICE_ID"; others use elevenlabs_voice_id.
    elevenlabs_voice_overrides: str = ""
    elevenlabs_model_id: str = "eleven_flash_v2_5"
    elevenlabs_output_format: str = "mp3_44100_64"
    # Credit guards (free plan = 10k characters/month). Cached audio doesn't count.
    tts_max_chars_per_request: int = 900
    tts_daily_chars_per_user: int = 1500
    tts_daily_chars_global: int = 2500
    stt_max_upload_bytes: int = 5_000_000
    voice_cache_dir: str = "voice_cache"

    # Guardrails
    prompt_guard_enabled: bool = True
    prompt_guard_model: str = "meta-llama/llama-prompt-guard-2-86m"
    prompt_guard_block_threshold: float = 0.9
    # Links in answers are kept only if they appear in retrieved content or use these domains.
    guard_allowed_link_domains: str = "consiva.ai"

    # Rate limits (in-memory, per backend process)
    rate_chat_per_minute: int = 12
    rate_chat_per_day: int = 200
    rate_voice_per_minute: int = 20
    rate_guest_sessions_per_hour: int = 20
    trust_proxy_headers: bool = False

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index_name: str = "consiva-knowledge-384"
    pinecone_namespace: str = "consiva-production"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # Retrieval tuning
    rag_top_k: int = 5
    rag_relevance_threshold: float = 0.81
    rag_max_context_chars: int = 6000

    # Database
    database_url: str = "sqlite:///./consiva.db"

    # Auth
    jwt_secret_key: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Language
    default_language: str = "en"
    supported_languages: str = "en,hi,es,fr,de,ar"

    # CORS
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5500,http://127.0.0.1:5500"
    frontend_url: str = "http://localhost:8000"

    @property
    def supported_languages_list(self) -> list[str]:
        return [l.strip() for l in self.supported_languages.split(",") if l.strip()]

    @property
    def elevenlabs_voice_overrides_map(self) -> dict[str, str]:
        pairs = (p.split(":", 1) for p in self.elevenlabs_voice_overrides.split(",") if ":" in p)
        return {lang.strip().lower(): voice.strip() for lang, voice in pairs if voice.strip()}

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
