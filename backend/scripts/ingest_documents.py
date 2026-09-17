"""Ingest approved Consiva documents into Pinecone.

Usage:
    python scripts/ingest_documents.py [--data-dir data] [--language en]

Supports PDF, DOCX, TXT, Markdown, HTML, and CSV files placed in the data
directory. Each chunk is deterministically hashed (document path + chunk
text) so re-running ingestion upserts existing vectors instead of creating
duplicates.
"""

import argparse
import csv
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from pypdf import PdfReader

from app.config import get_settings
from app.services.chunking import chunk_text, clean_text
from app.services.llm_client import embed_texts
from app.services.pinecone_client import ensure_index

settings = get_settings()

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown", ".html", ".htm", ".csv"}
EMBED_BATCH_SIZE = 32
# multilingual-e5-small reads at most 512 of its own tokens; 350 cl100k tokens leaves headroom
# for non-English text, which its tokenizer splits into more pieces.
CHUNK_TOKENS = 350
CHUNK_OVERLAP_TOKENS = 60
UPSERT_BATCH_SIZE = 100


def load_pdf(path: Path) -> list[tuple[str, int | None]]:
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((text, i))
    return pages


def load_docx(path: Path) -> list[tuple[str, int | None]]:
    doc = DocxDocument(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [(text, None)]


def load_text(path: Path) -> list[tuple[str, int | None]]:
    return [(path.read_text(encoding="utf-8", errors="ignore"), None)]


def load_html(path: Path) -> list[tuple[str, int | None]]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return [(soup.get_text(separator="\n"), None)]


def load_csv(path: Path) -> list[tuple[str, int | None]]:
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            line = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
            rows.append(line)
    return [("\n".join(rows), None)]


LOADERS = {
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".txt": load_text,
    ".md": load_text,
    ".markdown": load_text,
    ".html": load_html,
    ".htm": load_html,
    ".csv": load_csv,
}


def chunk_id(source_path: str, chunk_text_value: str) -> str:
    digest = hashlib.sha256(f"{source_path}::{chunk_text_value}".encode("utf-8")).hexdigest()
    return digest


def section_title_guess(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped) < 120:
            return stripped
    return None


def ingest_file(path: Path, language: str, source_url: str | None) -> list[dict]:
    loader = LOADERS[path.suffix.lower()]
    raw_sections = loader(path)

    records = []
    for raw_text, page_number in raw_sections:
        text = clean_text(raw_text)
        if not text:
            continue
        chunks = chunk_text(text, chunk_tokens=CHUNK_TOKENS, overlap_tokens=CHUNK_OVERLAP_TOKENS)
        for chunk in chunks:
            records.append(
                {
                    "id": chunk_id(str(path), chunk),
                    "text": chunk,
                    "document_name": path.name,
                    "file_path": str(path),
                    "page_number": page_number,
                    "section_title": section_title_guess(chunk),
                    "language": language,
                    "source_url": source_url,
                    "uploaded_at": datetime.now(timezone.utc).isoformat(),
                }
            )
    return records


def batched(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def main():
    parser = argparse.ArgumentParser(description="Ingest Consiva documents into Pinecone")
    parser.add_argument("--data-dir", default=str(Path(__file__).resolve().parent.parent / "data"))
    parser.add_argument("--language", default="en", help="Default language code for ingested documents")
    parser.add_argument("--source-url", default=None, help="Optional source URL to attach to all chunks")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        sys.exit(1)

    files = [p for p in data_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    if not files:
        print(f"No supported documents found in {data_dir} (supported: {sorted(SUPPORTED_EXTENSIONS)})")
        return

    print(f"Found {len(files)} document(s) to process.")
    index = ensure_index()

    all_records: list[dict] = []
    for path in files:
        try:
            records = ingest_file(path, args.language, args.source_url)
            print(f"  {path.name}: {len(records)} chunk(s)")
            all_records.extend(records)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED to process {path.name}: {exc}")

    if not all_records:
        print("No chunks produced, nothing to upsert.")
        return

    print(f"Embedding and upserting {len(all_records)} chunk(s) to Pinecone index '{settings.pinecone_index_name}'...")

    total_upserted = 0
    for batch in batched(all_records, EMBED_BATCH_SIZE):
        texts = [r["text"] for r in batch]
        vectors = embed_texts(texts)
        upsert_payload = [
            {
                "id": r["id"],
                "values": vec,
                "metadata": {k: v for k, v in r.items() if v is not None},
            }
            for r, vec in zip(batch, vectors)
        ]
        for sub_batch in batched(upsert_payload, UPSERT_BATCH_SIZE):
            index.upsert(vectors=sub_batch, namespace=settings.pinecone_namespace)
            total_upserted += len(sub_batch)
        print(f"  upserted {total_upserted}/{len(all_records)}")

    print("Ingestion complete.")


if __name__ == "__main__":
    main()
