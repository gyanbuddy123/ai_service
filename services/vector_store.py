"""
Qdrant vector store service.
- Collection: pdf_chunks (size=768, cosine distance)
- Payload fields: pdf_id, chapter_id, subject_id, class_id, page_number, chunk_index, text
- Embedding model: Vertex AI text-embedding-005 (768-dim)
"""
from __future__ import annotations

import logging
from functools import lru_cache

from config import settings

logger = logging.getLogger("ai_service.vector_store")

COLLECTION_NAME = "pdf_chunks"
EMBEDDING_DIM = 768
CHUNK_SIZE_CHARS = 1500
CHUNK_OVERLAP_CHARS = 200


@lru_cache(maxsize=1)
def _get_qdrant():
    from qdrant_client import QdrantClient
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection() -> None:
    """Create the pdf_chunks collection if it doesn't exist."""
    from qdrant_client.http.models import Distance, VectorParams, PayloadSchemaType

    client = _get_qdrant()
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME in existing:
        logger.info(f"Qdrant collection '{COLLECTION_NAME}' already exists")
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    # Create payload indexes for fast filtering
    client.create_payload_index(COLLECTION_NAME, "pdf_id", PayloadSchemaType.KEYWORD)
    client.create_payload_index(COLLECTION_NAME, "chapter_id", PayloadSchemaType.KEYWORD)
    logger.info(f"Qdrant collection '{COLLECTION_NAME}' created with payload indexes")


async def embed_text(text: str) -> list[float]:
    """Embed a single text using Vertex AI text-embedding-005."""
    import asyncio
    import vertexai
    from vertexai.language_models import TextEmbeddingModel

    vertexai.init(
        project=settings.google_cloud_project,
        location=settings.google_cloud_location_gemini,  # us-central1 supports embeddings
    )

    def _call():
        model = TextEmbeddingModel.from_pretrained("text-embedding-005")
        result = model.get_embeddings([text])
        return result[0].values

    return await asyncio.get_event_loop().run_in_executor(None, _call)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts — Vertex AI supports up to 250 per call."""
    import asyncio
    import vertexai
    from vertexai.language_models import TextEmbeddingModel

    vertexai.init(
        project=settings.google_cloud_project,
        location=settings.google_cloud_location_gemini,
    )

    def _call():
        model = TextEmbeddingModel.from_pretrained("text-embedding-005")
        results = model.get_embeddings(texts)
        return [r.values for r in results]

    return await asyncio.get_event_loop().run_in_executor(None, _call)


async def retrieve_context(
    chapter_id: str,
    query: str,
    top_k: int = 6,
) -> str:
    """
    Query Qdrant for the top-k most relevant chunks for a chapter.
    Returns them joined as a single context string.
    """
    import asyncio
    from qdrant_client.http.models import Filter, FieldCondition, MatchValue

    query_vector = await embed_text(query)
    client = _get_qdrant()

    def _search():
        return client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=Filter(
                must=[FieldCondition(key="chapter_id", match=MatchValue(value=chapter_id))]
            ),
            limit=top_k,
            with_payload=True,
        ).points

    results = await asyncio.get_event_loop().run_in_executor(None, _search)

    if not results:
        logger.warning(f"No Qdrant results for chapter_id={chapter_id}")
        return ""

    # Sort by page then chunk order, join text
    chunks = sorted(
        results,
        key=lambda r: (r.payload.get("page_number", 0), r.payload.get("chunk_index", 0)),
    )
    return "\n\n".join(r.payload.get("text", "") for r in chunks)


def chunk_pages(pages: list[dict], pdf_id: str, chapter_id: str) -> list[dict]:
    """Sliding-window character chunking with page metadata."""
    import uuid as _uuid

    full_text = ""
    page_boundaries: list[tuple[int, int]] = []

    for page in pages:
        start = len(full_text)
        full_text += page["text"] + "\n\n"
        page_boundaries.append((start, page["page_number"]))

    def page_for_offset(offset: int) -> int:
        page = page_boundaries[0][1]
        for char_start, page_num in page_boundaries:
            if offset >= char_start:
                page = page_num
            else:
                break
        return page

    chunks = []
    chunk_index = 0
    start = 0
    total_len = len(full_text)

    while start < total_len:
        end = min(start + CHUNK_SIZE_CHARS, total_len)
        chunk_text = full_text[start:end].strip()
        if chunk_text:
            chunks.append({
                "id": str(_uuid.uuid4()),
                "text": chunk_text,
                "page_number": page_for_offset(start),
                "chunk_index": chunk_index,
                "pdf_id": pdf_id,
                "chapter_id": chapter_id,
            })
            chunk_index += 1
        if end >= total_len:
            break
        start = end - CHUNK_OVERLAP_CHARS

    return chunks


async def embed_and_store(pdf_id: str, chapter_id: str, pages: list[dict]) -> int:
    """
    Full pipeline: chunk pages → embed → upsert to Qdrant.
    Returns number of chunks stored.
    """
    import asyncio
    import vertexai
    from vertexai.language_models import TextEmbeddingModel
    from qdrant_client.http.models import PointStruct

    chunks = chunk_pages(pages, pdf_id, chapter_id)
    if not chunks:
        logger.warning(f"No chunks generated for pdf_id={pdf_id}")
        return 0

    # Embed in batches of 50
    BATCH = 50
    all_texts = [c["text"] for c in chunks]
    all_vectors: list[list[float]] = []

    vertexai.init(
        project=settings.google_cloud_project,
        location=settings.google_cloud_location_gemini,
    )

    def _embed(texts):
        model = TextEmbeddingModel.from_pretrained("text-embedding-005")
        return [r.values for r in model.get_embeddings(texts)]

    for i in range(0, len(all_texts), BATCH):
        vectors = await asyncio.get_event_loop().run_in_executor(None, _embed, all_texts[i:i + BATCH])
        all_vectors.extend(vectors)

    # Upsert to Qdrant in batches of 100
    client = _get_qdrant()
    points = [
        PointStruct(
            id=chunk["id"],
            vector=vector,
            payload={
                "text": chunk["text"],
                "page_number": chunk["page_number"],
                "chunk_index": chunk["chunk_index"],
                "pdf_id": chunk["pdf_id"],
                "chapter_id": chunk["chapter_id"],
            },
        )
        for chunk, vector in zip(chunks, all_vectors)
    ]

    UPSERT_BATCH = 100
    for i in range(0, len(points), UPSERT_BATCH):
        client.upsert(collection_name=COLLECTION_NAME, points=points[i:i + UPSERT_BATCH])

    logger.info(f"Stored {len(points)} chunks for pdf_id={pdf_id}, chapter_id={chapter_id}")
    return len(points)


def delete_by_pdf_id(pdf_id: str) -> int:
    """
    Delete all vectors whose payload.pdf_id == pdf_id.
    Returns the number of points deleted.
    """
    from qdrant_client.http.models import Filter, FieldCondition, MatchValue, FilterSelector

    client = _get_qdrant()
    result = client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(
            filter=Filter(must=[FieldCondition(key="pdf_id", match=MatchValue(value=pdf_id))])
        ),
    )
    logger.info(f"Deleted Qdrant vectors for pdf_id={pdf_id}: {result}")
    return 1  # qdrant delete returns operation_id, not count
