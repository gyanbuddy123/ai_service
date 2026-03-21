import logging

from fastapi import APIRouter, HTTPException

from schemas.mcq import ModifyRequest, ModifyResponse
from services.llm_provider import mcq_service
from services.mcq_validator import validate_questions

router = APIRouter()
logger = logging.getLogger("ai_service.modify")


@router.post("/ai/modify", response_model=ModifyResponse)
async def modify_question(req: ModifyRequest):
    try:
        modified = await mcq_service.modify_question(
            question=req.question,
            modification_type=req.modification_type,
            instruction=req.instruction,
        )
    except Exception as exc:
        logger.error(f"Modify failed for session {req.session_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"LLM modification failed: {exc}")

    # Validate the modified question
    valid, rejected = validate_questions([modified])
    if rejected:
        logger.warning(
            f"Modified question failed validation: {rejected[0].get('rejection_reason')}"
        )
        # Return it anyway — log the issue but don't block the user
        return ModifyResponse(session_id=req.session_id, question=modified)

    return ModifyResponse(session_id=req.session_id, question=valid[0])
