"""
Imagen 3 image generation for question diagrams.
Replaces matplotlib-based diagram generation — works for all subjects
including biology, chemistry, geography, and physics diagrams.
"""
import asyncio
import base64
import io
import logging

logger = logging.getLogger("ai_service.imagen")

# Prefix injected before every prompt to keep images educational and answer-safe.
_SAFETY_PREFIX = (
    "Scientific diagram for a school exam question, clean white background, "
    "minimal line art style. Show ONLY the problem setup — never the answer. "
    "No text, no words, no letters, no numbers, no labels, no captions, no title. "
    "Simple clean lines only. "
)

# Suppresses hallucinated text, watermarks, and noisy artifacts.
_NEGATIVE_PROMPT = (
    "text, words, letters, numbers, labels, captions, title, watermark, "
    "signature, blurry, noisy, realistic photo, 3D render, shading, gradient"
)


async def generate_question_image(image_prompt: str) -> str | None:
    """
    Call Imagen 3 with the given image_prompt.
    Returns a base64-encoded PNG string, or None on failure.
    """
    from config import settings
    import vertexai
    from vertexai.preview.vision_models import ImageGenerationModel

    vertexai.init(
        project=settings.google_cloud_project,
        location=settings.google_cloud_location_gemini,
    )

    full_prompt = _SAFETY_PREFIX + image_prompt.strip()

    def _call() -> str | None:
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        images = model.generate_images(
            prompt=full_prompt,
            negative_prompt=_NEGATIVE_PROMPT,
            number_of_images=1,
            aspect_ratio="4:3",
        )
        if not images:
            return None
        buf = io.BytesIO()
        images[0]._pil_image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    try:
        return await asyncio.get_event_loop().run_in_executor(None, _call)
    except Exception as exc:
        logger.warning(f"Imagen generation failed: {exc}")
        return None
