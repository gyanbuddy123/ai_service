"""
Gemini 3.1 Flash Image generation for question diagrams.
Replaces Imagen 3 — uses a language model that understands the full question
context, knows the correct answer, and can be explicitly told what NOT to show.
"""
import asyncio
import base64
import logging

logger = logging.getLogger("ai_service.imagen")

# ── Image output standards ────────────────────────────────────────────────────
# Aspect ratio matches the app's question card layout (landscape, mobile-friendly)
_ASPECT_RATIO = "4:3"

# Output format — PNG for lossless diagram quality
_MIME_TYPE = "image/png"
# ─────────────────────────────────────────────────────────────────────────────

# ── Subject-aware style guidance ──────────────────────────────────────────────
# Each entry: (style instruction, label instruction)
# Matching is bidirectional substring (case-insensitive):
#   key in subject  OR  subject in key
# So "mathematics" matches "math", "applied mathematics", "mathematics", etc.
# Add new subjects here as needed — fallback is "default".
_SUBJECT_STYLES: dict[str, tuple[str, str]] = {
    # Precise line art — labels for given values/measurements are fine
    "mathematics": ("Clean technical line art, white background, precise geometry.",
                    "Label all given measurements and named points. Do NOT label or mark the unknown being solved."),
    "physics":     ("Clear scientific diagram, white background, line art style.",
                    "Label all given quantities and components. Do NOT show or hint at the answer value."),
    "chemistry":   ("Clear scientific diagram, white background.",
                    "Label all compounds, elements, and apparatus parts except the one being identified in the question."),

    # Detailed educational illustration — labels for non-answer structures expected
    "biology":     ("Detailed educational illustration, clean white background, textbook style.",
                    "Label all visible structures and parts EXCEPT the one the question is asking the student to identify."),
    "science":     ("Clear educational illustration, white background, textbook style.",
                    "Label all relevant parts except the specific element the question asks about."),

    # Map/realistic style — place names and features are part of the content
    "geography":   ("Informative map or diagram style, clean background.",
                    "Include relevant geographic labels, borders, and features. Do NOT label or highlight the specific answer location/feature."),
    "history":     ("Informative historical illustration or map, clean background.",
                    "Include relevant contextual labels and details. Do NOT label or identify the specific answer."),
    "social":      ("Informative illustration or map style, clean background.",
                    "Include relevant labels and contextual details. Do NOT reveal the answer directly."),

    # Fallback for any subject not matched above
    "default":     ("Clear educational diagram, white background.",
                    "Include labels that help the student understand the diagram. Do NOT label or reveal the answer."),
}


def _get_style(subject: str) -> tuple[str, str]:
    """
    Bidirectional substring match (case-insensitive):
      - key in subject  →  "mathematics" matches "applied mathematics"
      - subject in key  →  "mathematics" matches "math"
    Falls back to "default" if nothing matches.
    """
    subject_lower = subject.lower().strip()
    for key, style in _SUBJECT_STYLES.items():
        if key == "default":
            continue
        if key in subject_lower or subject_lower in key:
            return style
    return _SUBJECT_STYLES["default"]
# ─────────────────────────────────────────────────────────────────────────────


def _build_image_prompt(
    image_prompt: str,
    question_text: str,
    correct_answers: list[str],
    subject: str,
    grade_level: int,
) -> str:
    context_lines = []
    if subject:
        context_lines.append(f"Subject: {subject}")
    if grade_level:
        context_lines.append(f"Grade: {grade_level}")
    context = " | ".join(context_lines)

    answer_str = ", ".join(f'"{a}"' for a in correct_answers) if correct_answers else ""
    answer_warning = (
        f"\nCRITICAL: The correct answer is {answer_str}. "
        "DO NOT depict, suggest, label, or reveal this answer anywhere in the diagram."
        if answer_str else ""
    )

    style, label_rule = _get_style(subject)

    return f"""You are generating a diagram for an educational exam question.

{context}
Question: {question_text}{answer_warning}

Diagram to generate:
{image_prompt}

Style: {style}
Labelling: {label_rule}
- Show ONLY the problem setup, never the solution
- The diagram must be suitable for a Grade {grade_level} school exam"""


def _get_client():
    """Lazily initialise and cache the genai client (one per process)."""
    from config import settings
    from google import genai
    if not hasattr(_get_client, "_instance"):
        _get_client._instance = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.image_model_location,
        )
    return _get_client._instance


async def generate_question_image(
    image_prompt: str,
    question_text: str = "",
    correct_answers: list[str] | None = None,
    subject: str = "",
    grade_level: int = 0,
) -> str | None:
    """
    Call Gemini 3.1 Flash Image with full question context.
    Returns a base64-encoded PNG string, or None on failure.

    Output is standardised: 4:3 aspect ratio, 1024x768, PNG.
    """
    from config import settings
    from google.genai import types

    client = _get_client()

    prompt = _build_image_prompt(
        image_prompt=image_prompt.strip(),
        question_text=question_text,
        correct_answers=correct_answers or [],
        subject=subject,
        grade_level=grade_level,
    )

    def _call() -> str | None:
        if settings.image_model_api == "imagen":
            # Imagen 4 family — dedicated image generation API
            response = client.models.generate_images(
                model=settings.image_model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=_ASPECT_RATIO,
                    output_mime_type=_MIME_TYPE,
                ),
            )
            if not response.generated_images:
                return None
            return base64.b64encode(
                response.generated_images[0].image.image_bytes
            ).decode("utf-8")

        else:
            # Gemini image-capable models (gemini-3.1-flash-image-preview etc.)
            response = client.models.generate_content(
                model=settings.image_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=_ASPECT_RATIO,
                        output_mime_type=_MIME_TYPE,
                    ),
                ),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    return base64.b64encode(part.inline_data.data).decode("utf-8")
            return None

    try:
        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, _call),
            timeout=55.0,  # hard cap — keeps total modify response under Django's 120s timeout
        )
    except asyncio.TimeoutError:
        logger.warning("Gemini image generation timed out after 55s — returning None")
        return None
    except Exception as exc:
        logger.warning(f"Gemini image generation failed: {exc}", exc_info=True)
        return None
