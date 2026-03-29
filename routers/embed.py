import logging

from fastapi import APIRouter, HTTPException

from schemas.pdf import (
    EmbedRequest, EmbedResponse,
    DeleteEmbedResponse, ReactivateEmbedResponse, HardDeleteEmbedResponse,
)
from services.vector_store import (
    deactivate_by_pdf_id, reactivate_by_pdf_id, hard_delete_by_pdf_id,
)

router = APIRouter()
logger = logging.getLogger("ai_service.embed")


@router.post("/ai/embed", response_model=EmbedResponse)
async def embed_pdf(req: EmbedRequest):
    """
    Full PDF pipeline: download from GCS → extract text → chunk + embed + store in Qdrant.
    Django sends {pdf_id, chapter_id, gcs_path}; ai-service owns the entire pipeline.
    """
    from services.pdf_processor import process_pdf
    try:
        result = await process_pdf(
            pdf_id=req.pdf_id,
            chapter_id=req.chapter_id,
            gcs_path=req.gcs_path,
        )
    except Exception as exc:
        logger.error(f"embed_pdf failed for pdf_id={req.pdf_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"Embedding failed: {exc}")

    return EmbedResponse(
        pdf_id=req.pdf_id,
        total_pages=result["total_pages"],
        chunks_stored=result["chunks_stored"],
    )


@router.delete("/ai/embed/{pdf_id}", response_model=DeleteEmbedResponse)
async def deactivate_pdf_embeddings(pdf_id: str):
    """
    Soft-delete: set is_active=False on all Qdrant vectors for this pdf_id.
    Vectors stay in Qdrant but are excluded from context retrieval.
    """
    try:
        deactivate_by_pdf_id(pdf_id)
    except Exception as exc:
        logger.error(f"deactivate_by_pdf_id failed for pdf_id={pdf_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"Deactivation failed: {exc}")

    return DeleteEmbedResponse(pdf_id=pdf_id, deactivated=True)


@router.patch("/ai/embed/{pdf_id}/reactivate", response_model=ReactivateEmbedResponse)
async def reactivate_pdf_embeddings(pdf_id: str):
    """Restore: set is_active=True on all Qdrant vectors for this pdf_id."""
    try:
        reactivate_by_pdf_id(pdf_id)
    except Exception as exc:
        logger.error(f"reactivate_by_pdf_id failed for pdf_id={pdf_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"Reactivation failed: {exc}")

    return ReactivateEmbedResponse(pdf_id=pdf_id, reactivated=True)


@router.delete("/ai/embed/{pdf_id}/permanent", response_model=HardDeleteEmbedResponse)
async def permanently_delete_pdf_embeddings(pdf_id: str):
    """
    Permanent delete: remove all Qdrant vectors for this pdf_id.
    Use only for GDPR or permanent cleanup.
    """
    try:
        hard_delete_by_pdf_id(pdf_id)
    except Exception as exc:
        logger.error(f"hard_delete_by_pdf_id failed for pdf_id={pdf_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"Hard delete failed: {exc}")

    return HardDeleteEmbedResponse(pdf_id=pdf_id, deleted=True)
