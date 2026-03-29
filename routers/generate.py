import asyncio
import uuid
import logging

from fastapi import APIRouter, HTTPException

from schemas.mcq import GenerateRequest, GenerateResponse, GeneratedQuestion
from services.llm_provider import mcq_service
from services.prompt_builder import build_system_prompt, build_user_prompt, SUBMIT_MCQ_BATCH_TOOL
from services.mcq_validator import (
    validate_questions, validate_single, is_fixable, fix_instruction, question_hash,
)
from services.vector_store import resolve_context
from services.answer_shuffler import shuffle_answer_positions

router = APIRouter()
logger = logging.getLogger("ai_service.generate")

BATCH_SIZE = 10
MAX_FIX_ATTEMPTS = 1   # fix attempts per rejected question
MAX_RETRY_ROUNDS = 1   # regeneration rounds after fix pass


@router.post("/ai/generate", response_model=GenerateResponse)
async def generate_assessment(req: GenerateRequest):
    # ── 1. Resolve context: prefer Qdrant over inline text ──────────────────
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

    # ── 2. Phase 1: Initial batched generation ───────────────────────────────
    all_questions_raw: list[dict] = []
    model_used = "unknown"
    total_time_ms = 0
    remaining = req.num_questions

    while remaining > 0:
        batch_n = min(remaining, BATCH_SIZE)

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
            )
        except Exception as exc:
            logger.error(f"Generation failed for session {req.session_id}: {exc}")
            raise HTTPException(status_code=502, detail=f"LLM generation failed: {exc}")

        all_questions_raw.extend(raw.get("questions", []))
        model_used = raw.get("model_used", model_used)
        total_time_ms += raw.get("generation_time_ms", 0) or 0
        remaining -= batch_n

    valid, rejected = validate_questions(all_questions_raw)
    seen_hashes: set[str] = {
        question_hash(q["question_text"]) for q in valid if q.get("question_text")
    }
    logger.info(
        f"Session {req.session_id}: Phase 1 — {len(valid)} valid, {len(rejected)} rejected"
    )

    # ── 3. Phase 2: Fix pass — concurrent fix attempts for fixable rejections ─
    total_fix_attempts = 0
    fixable = [r for r in rejected if is_fixable(r.get("rejection_reason", ""))]

    if fixable:
        async def _try_fix(q: dict) -> dict | None:
            mod_type, instruction = fix_instruction(q["rejection_reason"])
            try:
                fixed = await mcq_service.modify_question(
                    question=q,
                    modification_type=mod_type,
                    instruction=instruction,
                    grade_level=req.grade_level,
                    subject=req.subject,
                    chapter=req.chapter,
                    topic=req.topic,
                    board=req.board,
                    context_text=context_text,
                )
                reason = validate_single(fixed, seen_hashes)
                if reason is None:
                    seen_hashes.add(question_hash(fixed["question_text"]))
                    return fixed
                logger.warning(
                    f"Session {req.session_id}: fix attempt still invalid: {reason}"
                )
            except Exception as exc:
                logger.warning(
                    f"Session {req.session_id}: fix attempt failed: {exc}"
                )
            return None

        fix_results = await asyncio.gather(*[_try_fix(q) for q in fixable])
        fixed_questions = [r for r in fix_results if r is not None]
        valid.extend(fixed_questions)
        total_fix_attempts = len(fixable)
        logger.info(
            f"Session {req.session_id}: Phase 2 — fixed {len(fixed_questions)}/{len(fixable)}"
        )

    # ── 4. Phase 3: Regen pass — one call to fill remaining gap ─────────────
    total_retry_rounds = 0
    still_needed = req.num_questions - len(valid)

    if still_needed > 0:
        retry_stems = list(req.existing_question_stems or []) + [
            q["question_text"] for q in valid if q.get("question_text")
        ]
        regen_user_prompt = build_user_prompt(
            chapter=req.chapter,
            topic=req.topic,
            num_questions=min(still_needed, BATCH_SIZE),
            context_text=context_text,
            existing_question_stems=retry_stems or None,
        )
        try:
            regen_raw = await mcq_service.generate(
                system_prompt=system_prompt,
                user_prompt=regen_user_prompt,
                tool_schema=SUBMIT_MCQ_BATCH_TOOL,
            )
            regen_valid, _ = validate_questions(
                regen_raw.get("questions", []), seen_hashes
            )
            valid.extend(regen_valid)
            model_used = regen_raw.get("model_used", model_used)
            total_time_ms += regen_raw.get("generation_time_ms", 0) or 0
            total_retry_rounds = 1
            logger.info(
                f"Session {req.session_id}: Phase 3 regen — "
                f"+{len(regen_valid)} questions"
            )
        except Exception as exc:
            logger.warning(
                f"Session {req.session_id}: regen pass failed: {exc}"
            )

    # ── 5. Internal cross-model verification + repair ────────────────────────
    try:
        from services.question_verifier import verify_and_improve
        valid = await verify_and_improve(
            questions=valid,
            context_text=context_text,
            seen_hashes=seen_hashes,
            mcq_service=mcq_service,
            grade_level=req.grade_level,
            subject=req.subject,
            chapter=req.chapter,
            topic=req.topic,
            board=req.board,
        )
    except Exception as exc:
        logger.warning(f"Session {req.session_id}: verification step failed (non-fatal): {exc}")

    # ── 6. Shuffle answer positions ──────────────────────────────────────────
    valid = shuffle_answer_positions(valid)

    # ── 7. Execute matplotlib diagrams ──────────────────────────────────────
    for q in valid:
        code = q.get("matplotlib_code", "")
        if code:
            try:
                from services.matplotlib_executor import sanitize_matplotlib_code, execute_matplotlib_code
                sanitized = sanitize_matplotlib_code(code.strip())
                if sanitized:
                    result = execute_matplotlib_code(sanitized)
                    q["image_base64"] = result.get("image_base64")
                    if result.get("error"):
                        logger.warning(
                            f"Session {req.session_id}: matplotlib execution error: {result['error']}"
                        )
            except Exception as exc:
                logger.warning(
                    f"Session {req.session_id}: matplotlib execution failed: {exc}"
                )
                q["image_base64"] = None

    # ── 8. Build response ────────────────────────────────────────────────────
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
        _EXP_BY_DIFFICULTY = {1: 5, 2: 5, 3: 10, 4: 15, 5: 20}
        q.setdefault("exp_points", _EXP_BY_DIFFICULTY.get(q.get("difficulty_level"), 10))
        q["question_order"] = i + 1
        questions_out.append(GeneratedQuestion(**q))

    return GenerateResponse(
        session_id=req.session_id,
        questions=questions_out,
        model_used=model_used,
        generation_time_ms=total_time_ms,
        rejected_count=req.num_questions - len(valid),
        total_fix_attempts=total_fix_attempts,
        total_retry_rounds=total_retry_rounds,
        warning=warning,
    )
