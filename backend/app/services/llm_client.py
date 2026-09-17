"""LLM (Groq, chat completions) and embeddings (local multilingual-e5-small, int8 ONNX) clients."""

from pathlib import Path
from threading import Lock

import numpy as np
from openai import OpenAI

from app.config import get_settings

settings = get_settings()

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """OpenAI-compatible client pointed at Groq for chat completions."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    return _client


# The ONNX session and tokenizer are loaded once per process (lazily, guarded by a lock)
# since FastAPI may serve concurrent requests. No torch needed: onnxruntime + tokenizers.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_MAX_TOKENS = 512
_model = None
_model_lock = Lock()


def _resolve_model_dir() -> Path:
    path = Path(settings.embedding_model_dir)
    return path if path.is_absolute() else _BACKEND_DIR / path


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            import onnxruntime as ort
            from tokenizers import Tokenizer

            model_dir = _resolve_model_dir()
            tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
            tokenizer.enable_truncation(max_length=_MAX_TOKENS)
            tokenizer.enable_padding(pad_id=tokenizer.token_to_id("<pad>") or 1, pad_token="<pad>")
            session = ort.InferenceSession(
                str(model_dir / settings.embedding_model_file), providers=["CPUExecutionProvider"]
            )
            input_names = {i.name for i in session.get_inputs()}
            _model = (tokenizer, session, input_names)
    return _model


def _embed(texts: list[str]) -> list[list[float]]:
    tokenizer, session, input_names = _load_model()
    encodings = tokenizer.encode_batch(texts)
    input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
    feeds = {"input_ids": input_ids, "attention_mask": attention_mask}
    if "token_type_ids" in input_names:
        feeds["token_type_ids"] = np.zeros_like(input_ids)

    last_hidden_state = session.run(None, feeds)[0]
    # Mean pooling over real tokens, then L2-normalise (as recommended for e5 models).
    mask = attention_mask[..., None].astype(np.float32)
    pooled = (last_hidden_state * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
    pooled /= np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
    return pooled.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed knowledge-base passages. e5 models require the "passage: " prefix."""
    return _embed([f"passage: {t}" for t in texts])


def embed_query(text: str) -> list[float]:
    """Embed a user search query. e5 models require the "query: " prefix."""
    return _embed([f"query: {text}"])[0]
