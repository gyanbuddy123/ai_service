"""
LLM provider for MCQ generation and modification.
Single provider: Gemini 2.5 Pro via Vertex AI.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from config import settings
from services.prompt_builder import QUESTION_ITEM_SCHEMA

logger = logging.getLogger("ai_service.llm")


class GeminiProvider:
    def __init__(self):
        import vertexai
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location_gemini,
        )
        self.model_name = settings.gemini_model

    async def generate_mcqs(self, system_prompt: str, user_prompt: str) -> dict:
        from vertexai.generative_models import GenerativeModel, GenerationConfig

        gemini_schema = {
            "type": "object",
            "properties": {"questions": {"type": "array", "items": QUESTION_ITEM_SCHEMA}},
            "required": ["questions"],
        }

        combined_prompt = (
            f"{system_prompt}\n\n"
            "Return your response as a JSON object with a 'questions' array. "
            "No markdown, no code fences, only the raw JSON object.\n\n"
            f"{user_prompt}"
        )

        def _call():
            model = GenerativeModel(self.model_name)
            return model.generate_content(
                combined_prompt,
                generation_config=GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=65536,
                    response_mime_type="application/json",
                    response_schema=gemini_schema,
                ),
            )

        response = await asyncio.get_event_loop().run_in_executor(None, _call)
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            finish_reason = (
                getattr(response.candidates[0], "finish_reason", "unknown")
                if response.candidates else "unknown"
            )
            logger.error(
                f"Gemini JSON parse failed (finish_reason={finish_reason}): {e} "
                f"— response length={len(response.text)}"
            )
            raise ValueError(f"Gemini returned invalid JSON (finish_reason={finish_reason}): {e}")
        return {"questions": data.get("questions", [])}

    async def fix_mcqs_batch(self, system_prompt: str, user_prompt: str) -> list[dict]:
        from vertexai.generative_models import GenerativeModel, GenerationConfig

        batch_schema = {
            "type": "object",
            "properties": {"questions": {"type": "array", "items": QUESTION_ITEM_SCHEMA}},
            "required": ["questions"],
        }

        combined = (
            f"{system_prompt}\n\n{user_prompt}\n\n"
            "Return the fixed questions as a JSON object with a 'questions' array."
        )

        def _call():
            model = GenerativeModel(self.model_name)
            return model.generate_content(
                combined,
                generation_config=GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=65536,
                    response_mime_type="application/json",
                    response_schema=batch_schema,
                ),
            )

        response = await asyncio.get_event_loop().run_in_executor(None, _call)
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            finish_reason = (
                getattr(response.candidates[0], "finish_reason", "unknown")
                if response.candidates else "unknown"
            )
            logger.error(
                f"Gemini batch fix JSON parse failed (finish_reason={finish_reason}): {e} "
                f"— response length={len(response.text)}"
            )
            raise ValueError(f"Gemini batch fix returned invalid JSON (finish_reason={finish_reason}): {e}")
        return data.get("questions", [])

    async def modify(self, system: str, user: str) -> dict:
        from vertexai.generative_models import GenerativeModel, GenerationConfig

        combined = f"{system}\n\n{user}\n\nReturn only the modified question as a raw JSON object."

        def _call():
            model = GenerativeModel(self.model_name)
            return model.generate_content(
                combined,
                generation_config=GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=65536,
                    response_mime_type="application/json",
                    response_schema=QUESTION_ITEM_SCHEMA,
                ),
            )

        response = await asyncio.get_event_loop().run_in_executor(None, _call)
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            finish_reason = (
                getattr(response.candidates[0], "finish_reason", "unknown")
                if response.candidates else "unknown"
            )
            logger.error(
                f"Gemini modify JSON parse failed (finish_reason={finish_reason}): {e} "
                f"— response length={len(response.text)}"
            )
            raise ValueError(f"Gemini modify returned invalid JSON (finish_reason={finish_reason}): {e}")
        return data


class MCQGenerationService:
    def __init__(self):
        self._provider: GeminiProvider | None = None

    def _get_provider(self) -> GeminiProvider:
        if self._provider is None:
            self._provider = GeminiProvider()
        return self._provider

    async def generate(self, system_prompt: str, user_prompt: str) -> dict:
        start = time.monotonic()
        result = await self._get_provider().generate_mcqs(system_prompt, user_prompt)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"Gemini generation succeeded ({len(result['questions'])} questions) in {elapsed_ms}ms")
        result["generation_time_ms"] = elapsed_ms
        return result

    async def fix_questions_batch(self, system_prompt: str, user_prompt: str) -> list[dict]:
        start = time.monotonic()
        fixed = await self._get_provider().fix_mcqs_batch(system_prompt, user_prompt)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"Batch fix returned {len(fixed)} questions in {elapsed_ms}ms")
        return fixed

    async def modify(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Modify a single question via Gemini.
        Prompt building and response post-processing are done by the caller.
        Returns the raw parsed question dict from Gemini.
        """
        start = time.monotonic()
        result = await self._get_provider().modify(system_prompt, user_prompt)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"Gemini modify succeeded in {elapsed_ms}ms")
        return result


# Singleton used by routers
mcq_service = MCQGenerationService()
