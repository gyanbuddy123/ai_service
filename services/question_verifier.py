"""
Internal cross-model verification of generated MCQ questions.
Always uses Gemini as the checker model (cross-model verification principle).
Flagged questions are passed back to modify_question for one repair attempt.
No verification fields are exposed in the API response — this is purely internal.
"""
from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger("ai_service.verifier")

_VERIFY_SYSTEM = """You are an expert educational content auditor.
You will receive a list of MCQ questions and the source chapter content they were generated from.
Review each question and flag ONLY those with clear, specific issues.

Check each question for:
1. CORRECTNESS — Is the marked correct answer actually correct per the chapter content?
2. CLARITY — Is the question text unambiguous and free from misleading phrasing?
3. HINT QUALITY — Does the hint reveal or strongly imply the correct answer?
4. DISTRACTOR QUALITY — Are wrong options clearly wrong to a knowledgeable student?
   (For rearrange type: is the correct_order logically sound?)

Be strict on correctness and hint quality. Be lenient on style.
Only flag questions that have a definite, fixable problem — not stylistic preferences.
If a question is fine, do NOT include it in flagged.
"""


def _verification_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "flagged": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "issues": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["index", "issues"],
                },
            }
        },
        "required": ["flagged"],
    }


async def _verify_batch_gemini(
    questions_json: str,
    context_text: str,
) -> list[dict]:
    """
    Call Gemini to verify a batch of questions.
    Returns list of {index, issues} for flagged questions only.
    """
    from config import settings
    import vertexai
    from vertexai.generative_models import GenerativeModel, GenerationConfig

    vertexai.init(
        project=settings.google_cloud_project,
        location=settings.google_cloud_location_gemini,
    )

    context_excerpt = context_text[:8000] if context_text else "(no context provided)"

    user_prompt = (
        f"Chapter content:\n---\n{context_excerpt}\n---\n\n"
        f"Questions to review (JSON array):\n{questions_json}\n\n"
        "Return flagged questions only. An empty flagged array means all questions are acceptable."
    )

    combined = f"{_VERIFY_SYSTEM}\n\n{user_prompt}"

    def _call():
        model = GenerativeModel(settings.gemini_model)
        return model.generate_content(
            combined,
            generation_config=GenerationConfig(
                temperature=0.1,
                max_output_tokens=4096,
                response_mime_type="application/json",
                response_schema=_verification_schema(),
            ),
        )

    response = await asyncio.get_event_loop().run_in_executor(None, _call)
    data = json.loads(response.text)
    return data.get("flagged", [])


async def verify_and_improve(
    questions: list[dict],
    context_text: str,
    seen_hashes: set[str],
    mcq_service,  # MCQGenerationService — avoid circular import
    grade_level: int = 8,
    subject: str = "",
    chapter: str = "",
    topic: str = "",
    board: str = "CBSE",
) -> list[dict]:
    """
    Verify all questions with Gemini and attempt one fix for any flagged question.
    Questions that cannot be fixed are kept as-is (validation already passed for them).
    Modifies the questions list in-place and returns it.
    """
    if not questions:
        return questions

    BATCH_SIZE = 10
    all_flagged: list[dict] = []

    # Run verification in batches of 10 (avoid token limits)
    for batch_start in range(0, len(questions), BATCH_SIZE):
        batch = questions[batch_start: batch_start + BATCH_SIZE]
        # Include only fields relevant to verification (no image_base64)
        slim_batch = [
            {k: v for k, v in q.items() if k != "image_base64" and k != "matplotlib_code"}
            for q in batch
        ]
        try:
            flagged = await _verify_batch_gemini(
                questions_json=json.dumps(slim_batch, indent=2),
                context_text=context_text,
            )
            # Offset indices to global question list
            for f in flagged:
                all_flagged.append({
                    "global_index": batch_start + f["index"],
                    "issues": f.get("issues", []),
                })
        except Exception as exc:
            logger.warning(f"Verification batch [{batch_start}:{batch_start + BATCH_SIZE}] failed: {exc}")
            continue

    if not all_flagged:
        logger.info(f"Verification: all {len(questions)} questions passed")
        return questions

    logger.info(f"Verification: {len(all_flagged)}/{len(questions)} questions flagged for repair")

    from services.mcq_validator import validate_single, question_hash

    # Attempt one fix per flagged question (concurrent)
    async def _try_repair(global_index: int, issues: list[str]) -> tuple[int, dict | None]:
        q = questions[global_index]
        issues_text = "; ".join(issues)
        instruction = (
            f"The following issues were found by an independent reviewer: {issues_text}. "
            "Fix each issue. Keep the question on the same topic and at the same difficulty level. "
            "Preserve the question type and structure."
        )
        try:
            fixed = await mcq_service.modify_question(
                question=q,
                modification_type="CUSTOM",
                instruction=instruction,
                grade_level=grade_level,
                subject=subject,
                chapter=chapter,
                topic=topic,
                board=board,
                context_text=context_text,
            )
            # Only accept if the fix passes structural validation
            reason = validate_single(fixed, seen_hashes)
            if reason is None:
                seen_hashes.add(question_hash(fixed["question_text"]))
                logger.info(f"Verifier repair succeeded for question index {global_index}")
                return global_index, fixed
            else:
                logger.warning(
                    f"Verifier repair for index {global_index} still invalid ({reason}), keeping original"
                )
        except Exception as exc:
            logger.warning(f"Verifier repair failed for index {global_index}: {exc}")
        return global_index, None

    repair_tasks = [_try_repair(f["global_index"], f["issues"]) for f in all_flagged]
    repair_results = await asyncio.gather(*repair_tasks)

    for global_index, fixed in repair_results:
        if fixed is not None:
            questions[global_index] = fixed

    return questions
