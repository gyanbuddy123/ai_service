import uuid
import logging

from fastapi import APIRouter, HTTPException

from schemas.mcq import GenerateRequest, GenerateResponse, GeneratedQuestion
from services.llm_provider import mcq_service
from services.prompt_builder import build_system_prompt, build_user_prompt, SUBMIT_MCQ_BATCH_TOOL
from services.mcq_validator import validate_questions

router = APIRouter()
logger = logging.getLogger("ai_service.generate")


@router.post("/ai/generate", response_model=GenerateResponse)
async def generate_assessment(req: GenerateRequest):
    system_prompt = build_system_prompt(req.grade_level)
    user_prompt = build_user_prompt(
        topic=req.topic,
        num_questions=req.num_questions,
        context_text=req.context_text,
        difficulty_distribution=req.difficulty_distribution,
    )

    try:
        raw = await mcq_service.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_schema=SUBMIT_MCQ_BATCH_TOOL,
            num_questions=req.num_questions,
        )
    except Exception as exc:
        logger.error(f"Generation failed for session {req.session_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {exc}")

    valid, rejected = validate_questions(raw.get("questions", []))
    logger.info(
        f"Session {req.session_id}: {len(valid)} valid, {len(rejected)} rejected"
    )

    # Assign stable client-side IDs and order
    questions_out = []
    for i, q in enumerate(valid):
        q.setdefault("id", f"q_{uuid.uuid4().hex[:12]}")
        q["question_order"] = i + 1
        questions_out.append(q)

    return GenerateResponse(
        session_id=req.session_id,
        questions=[GeneratedQuestion(**q) for q in questions_out],
        model_used=raw.get("model_used", "unknown"),
        generation_time_ms=raw.get("generation_time_ms"),
        rejected_count=len(rejected),
    )
