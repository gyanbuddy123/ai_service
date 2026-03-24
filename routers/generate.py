import uuid
import logging

from fastapi import APIRouter, HTTPException

from schemas.mcq import GenerateRequest, GenerateResponse, GeneratedQuestion
from services.llm_provider import mcq_service
from services.prompt_builder import build_system_prompt, build_user_prompt, SUBMIT_MCQ_BATCH_TOOL
from services.mcq_validator import validate_questions
from services.vector_store import retrieve_context

router = APIRouter()
logger = logging.getLogger("ai_service.generate")


@router.post("/ai/generate", response_model=GenerateResponse)
async def generate_assessment(req: GenerateRequest):
    # Resolve context: prefer Qdrant over inline text
    context_text = req.context_text  # may be empty string
    if req.chapter_id:
        try:
            qdrant_context = await retrieve_context(
                chapter_id=req.chapter_id,
                query=req.topic,
            )
            if qdrant_context:
                context_text = qdrant_context
                logger.info(
                    f"Session {req.session_id}: using Qdrant context "
                    f"({len(qdrant_context)} chars) for chapter {req.chapter_id}"
                )
            else:
                logger.info(
                    f"Session {req.session_id}: no Qdrant chunks for chapter "
                    f"{req.chapter_id}, falling back to inline context_text"
                )
        except Exception as exc:
            logger.warning(
                f"Qdrant retrieval failed for chapter {req.chapter_id}: {exc} — "
                "falling back to inline context_text"
            )

    if not context_text:
        raise HTTPException(
            status_code=422,
            detail=(
                "No context available for generation. "
                "Upload a PDF for this chapter or provide context_text."
            ),
        )

    system_prompt = build_system_prompt(
        grade_level=req.grade_level,
        subject=req.subject,
        chapter=req.chapter,
        board=req.board,
    )

    # Batch into chunks of 10 to avoid LLM output token limits
    BATCH_SIZE = 10
    all_questions_raw: list[dict] = []
    total_rejected: list[dict] = []
    model_used = "unknown"
    total_time_ms = 0
    remaining = req.num_questions

    while remaining > 0:
        batch_n = min(remaining, BATCH_SIZE)

        # Include already-generated stems to avoid intra-run duplicates
        all_stems = list(req.existing_question_stems or []) + [
            q["question_text"] for q in all_questions_raw if q.get("question_text")
        ]

        user_prompt = build_user_prompt(
            chapter=req.chapter,
            topic=req.topic,
            num_questions=batch_n,
            context_text=context_text,
            existing_question_stems=all_stems or None,
        )
        try:
            raw = await mcq_service.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tool_schema=SUBMIT_MCQ_BATCH_TOOL,
                num_questions=batch_n,
            )
        except Exception as exc:
            logger.error(f"Generation failed for session {req.session_id}: {exc}")
            raise HTTPException(status_code=502, detail=f"LLM generation failed: {exc}")

        all_questions_raw.extend(raw.get("questions", []))
        model_used = raw.get("model_used", model_used)
        total_time_ms += raw.get("generation_time_ms", 0)
        remaining -= batch_n

    valid, rejected = validate_questions(all_questions_raw)
    logger.info(f"Session {req.session_id}: {len(valid)} valid, {len(rejected)} rejected")
    for r in rejected:
        logger.warning(f"Rejected question: {r.get('rejection_reason')} | keys: {list(r.keys())} | sample: {str(r)[:300]}")

    questions_out = []
    for i, q in enumerate(valid):
        q.setdefault("id", f"q_{uuid.uuid4().hex[:12]}")
        q.setdefault("question_type", "mcq_single")
        q.setdefault("exp_points", 10)
        q["question_order"] = i + 1
        questions_out.append(GeneratedQuestion(**q))

    return GenerateResponse(
        session_id=req.session_id,
        questions=questions_out,
        model_used=model_used,
        generation_time_ms=total_time_ms,
        rejected_count=len(rejected),
    )
