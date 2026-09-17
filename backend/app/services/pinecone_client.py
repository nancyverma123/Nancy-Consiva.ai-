from pinecone import Pinecone, ServerlessSpec

from app.config import get_settings

settings = get_settings()

_pc: Pinecone | None = None


def get_pinecone() -> Pinecone:
    global _pc
    if _pc is None:
        _pc = Pinecone(api_key=settings.pinecone_api_key)
    return _pc


def ensure_index():
    pc = get_pinecone()
    existing = [idx["name"] for idx in pc.list_indexes()]
    if settings.pinecone_index_name not in existing:
        pc.create_index(
            name=settings.pinecone_index_name,
            dimension=settings.embedding_dimensions,
            metric="cosine",
            spec=ServerlessSpec(cloud=settings.pinecone_cloud, region=settings.pinecone_region),
        )
    return pc.Index(settings.pinecone_index_name)


def get_index():
    pc = get_pinecone()
    return pc.Index(settings.pinecone_index_name)
