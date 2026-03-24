import logging

from fastapi import APIRouter, HTTPException

from schemas.pdf import EmbedRequest, EmbedResponse, DeleteEmbedResponse
from services.vector_store import embed_and_store, delete_by_pdf_id

router = APIRouter()
logger = logging.getLogger("ai_service.embed")


@router.post("/ai/embed", response_model=EmbedResponse)
async def embed_pdf(req: EmbedRequest):
    """Chunk, embed and store PDF pages into Qdrant."""
    pages = [p.model_dump() for p in req.pages]
    try:
        chunks_stored = await embed_and_store(
            pdf_id=req.pdf_id,
            chapter_id=req.chapter_id,
            pages=pages,
        )
    except Exception as exc:
        logger.error(f"embed_and_store failed for pdf_id={req.pdf_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"Embedding failed: {exc}")

    return EmbedResponse(pdf_id=req.pdf_id, chunks_stored=chunks_stored)


@router.delete("/ai/embed/{pdf_id}", response_model=DeleteEmbedResponse)
async def delete_pdf_embeddings(pdf_id: str):
    """Delete all Qdrant vectors for a pdf_id."""
    try:
        delete_by_pdf_id(pdf_id)
    except Exception as exc:
        logger.error(f"delete_by_pdf_id failed for pdf_id={pdf_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"Delete failed: {exc}")

    return DeleteEmbedResponse(pdf_id=pdf_id, deleted=True)
