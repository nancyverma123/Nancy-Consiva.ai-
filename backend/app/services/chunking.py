import re

import tiktoken

_encoding = tiktoken.get_encoding("cl100k_base")


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_tokens: int = 650, overlap_tokens: int = 100) -> list[str]:
    """Split text into chunks of ~chunk_tokens with ~overlap_tokens overlap."""
    tokens = _encoding.encode(text)
    if not tokens:
        return []

    chunks: list[str] = []
    start = 0
    step = max(chunk_tokens - overlap_tokens, 1)
    while start < len(tokens):
        end = min(start + chunk_tokens, len(tokens))
        chunk = _encoding.decode(tokens[start:end])
        stripped = chunk.strip()
        if stripped:
            chunks.append(stripped)
        if end == len(tokens):
            break
        start += step
    return chunks
