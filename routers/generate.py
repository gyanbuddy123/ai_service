import asyncio
import uuid
import logging

from fastapi import APIRouter, HTTPException

from schemas.mcq import GenerateRequest, GenerateResponse, GeneratedQuestion
from services.llm_provider import mcq_service
from services.prompt_builder import build_system_prompt, build_user_prompt, build_batch_fix_prompt
from services.mcq_validator import (
    validate_questions, validate_single, question_hash, build_fix_instruction,
)
from services.vector_store import resolve_context
from services.answer_shuffler import shuffle_answer_positions

router = APIRouter()
logger = logging.getLogger("ai_service.generate")


@router.post("/ai/generate", response_model=GenerateResponse)
async def generate_assessment(req: GenerateRequest):
    # ── 1. Resolve context ───────────────────────────────────────────────────
    context_text = await resolve_context(
        chapter_id=req.chapter_id,
        query=req.topic or req.chapter,
        fallback_text=req.context_text,
        log_prefix=f"Session {req.session_id}: ",
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

    # ── 2. Single generation call ────────────────────────────────────────────
    # Buffer scales with requested count: +1 for ≤5, +2 for ≤10, +3 for ≤15, etc.
    _buffer = (req.num_questions - 1) // 5 + 1
    user_prompt = build_user_prompt(
        chapter=req.chapter,
        topic=req.topic,
        num_questions=req.num_questions + _buffer,  # over-generate to absorb expected rejections
        context_text=context_text,
        existing_question_stems=req.existing_question_stems or None,
    )
    try:
        raw = await mcq_service.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    except Exception as exc:
        logger.error(f"Generation failed for session {req.session_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {exc}")

    total_time_ms = raw.get("generation_time_ms", 0) or 0

    valid, rejected = validate_questions(raw.get("questions", []))
    seen_hashes: set[str] = {
        question_hash(q["question_text"]) for q in valid if q.get("question_text")
    }
    logger.info(
        f"Session {req.session_id}: {len(valid)} valid, {len(rejected)} rejected"
    )

    # ── 3. Batch fix pass — fix ALL rejected questions in one LLM call ───────
    if rejected:
        fix_items = [
            {
                "index": i,
                "fix_instruction": build_fix_instruction(q.get("rejection_reason", ""), q),
                "question": {k: v for k, v in q.items() if k != "rejection_reason"},
            }
            for i, q in enumerate(rejected)
        ]
        try:
            initial_valid_count = len(valid)
            fix_user_prompt = build_batch_fix_prompt(fix_items)
            fixed_list = await mcq_service.fix_questions_batch(system_prompt, fix_user_prompt)
            for fixed in fixed_list:
                reason = validate_single(fixed, seen_hashes)
                if reason is None:
                    seen_hashes.add(question_hash(fixed["question_text"]))
                    valid.append(fixed)
                else:
                    logger.warning(
                        f"Session {req.session_id}: batch-fixed question still invalid: {reason}"
                    )
            logger.info(
                f"Session {req.session_id}: batch fix — {len(fixed_list)} returned, "
                f"{len(valid) - initial_valid_count} accepted"
            )
        except Exception as exc:
            logger.warning(f"Session {req.session_id}: batch fix failed: {exc}")

    # Trim to requested count (over-generation buffer may produce extras)
    valid = valid[: req.num_questions]

    # ── 4. Shuffle answer positions ──────────────────────────────────────────
    valid = shuffle_answer_positions(valid)

    # ── 6. Finalize questions (exp_points sync + Gemini image generation) ──
    # Run concurrently — image calls per question are independent I/O
    from services.question_utils import finalize_question
    await asyncio.gather(
        *[finalize_question(
            q,
            log_prefix=f"Session {req.session_id}: ",
            subject=req.subject,
            grade_level=req.grade_level,
        ) for q in valid]
    )

    # ── 7. Build response ────────────────────────────────────────────────────
    warning = None
    if len(valid) < req.num_questions:
        warning = (
            f"Requested {req.num_questions} questions but only "
            f"{len(valid)} could be generated after fix and retry."
        )
        logger.warning(f"Session {req.session_id}: {warning}")

    questions_out = []
    for i, q in enumerate(valid):
        q.setdefault("id", f"q_{uuid.uuid4().hex[:12]}")
        q.setdefault("question_type", "mcq_single")
        q["question_order"] = i + 1
        questions_out.append(GeneratedQuestion(**q))

    return GenerateResponse(
        session_id=req.session_id,
        questions=questions_out,
        generation_time_ms=total_time_ms,
        rejected_count=req.num_questions - len(valid),
        warning=warning,
    )
