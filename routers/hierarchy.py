import logging

from fastapi import APIRouter, HTTPException

from schemas.hierarchy import ExtractHierarchyRequest, ExtractHierarchyResponse

router = APIRouter()
logger = logging.getLogger("ai_service.hierarchy")


@router.post("/ai/extract-hierarchy", response_model=ExtractHierarchyResponse)
async def extract_hierarchy_endpoint(req: ExtractHierarchyRequest):
    """
    "Create Chapter with PDF": download the job's PDF/ZIP from GCS, extract text
    per PDF, and infer a Module/Chapter hierarchy via OpenAI. Returns structured
    rows only — no Excel is built; Django persists directly using the same
    logic as Import Excel.
    """
    from services.hierarchy_extractor import extract_hierarchy
    try:
        result = await extract_hierarchy(
            job_id=req.job_id,
            gcs_path=req.gcs_path,
            subject_name=req.subject_name,
        )
    except Exception as exc:
        logger.error(f"extract_hierarchy failed for job_id={req.job_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"Hierarchy extraction failed: {exc}")

    return ExtractHierarchyResponse(**result)
