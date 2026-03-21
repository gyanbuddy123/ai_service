"""
LLM providers for MCQ generation.
Primary: Claude Sonnet 4.6 via Vertex AI (tool_use mode)
Fallback: Gemini 2.0 Flash via Vertex AI
"""
from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod

from config import settings

logger = logging.getLogger("ai_service.llm")


class LLMProvider(ABC):
    @abstractmethod
    async def generate_mcqs(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_schema: dict,
        num_questions: int,
    ) -> dict:
        """Return a dict with 'questions' list and 'model_used' str."""
        ...


class ClaudeVertexProvider(LLMProvider):
    def __init__(self):
        from anthropic import AnthropicVertex
        self._client = AnthropicVertex(
            region=settings.google_cloud_location_claude,
            project_id=settings.google_cloud_project,
        )
        self.model = settings.claude_model

    async def generate_mcqs(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_schema: dict,
        num_questions: int,
    ) -> dict:
        import asyncio

        def _call():
            return self._client.messages.create(
                model=self.model,
                max_tokens=8192,
                temperature=0.3,
                system=system_prompt,
                tools=[tool_schema],
                tool_choice={"type": "any"},
                messages=[{"role": "user", "content": user_prompt}],
            )

        response = await asyncio.get_event_loop().run_in_executor(None, _call)

        # Extract tool_use block
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_mcq_batch":
                return {
                    "questions": block.input.get("questions", []),
                    "model_used": self.model,
                }

        raise ValueError("Claude did not return a tool_use block")


class GeminiProvider(LLMProvider):
    def __init__(self):
        import vertexai
        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location_gemini,
        )
        self.model_name = settings.gemini_model

    async def generate_mcqs(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_schema: dict,
        num_questions: int,
    ) -> dict:
        import asyncio
        import json
        from vertexai.generative_models import GenerativeModel, GenerationConfig

        combined_prompt = (
            f"{system_prompt}\n\n"
            "Output valid JSON with a 'questions' array matching the submit_mcq_batch schema. "
            "No markdown, no code fences, only the raw JSON object.\n\n"
            f"{user_prompt}"
        )

        schema = {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {"type": "object"},
                }
            },
            "required": ["questions"],
        }

        def _call():
            model = GenerativeModel(self.model_name)
            return model.generate_content(
                combined_prompt,
                generation_config=GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )

        response = await asyncio.get_event_loop().run_in_executor(None, _call)
        data = json.loads(response.text)
        return {"questions": data.get("questions", []), "model_used": self.model_name}


class MCQGenerationService:
    def __init__(self):
        self._primary: ClaudeVertexProvider | None = None
        self._fallback: GeminiProvider | None = None

    def _get_primary(self) -> ClaudeVertexProvider:
        if self._primary is None:
            self._primary = ClaudeVertexProvider()
        return self._primary

    def _get_fallback(self) -> GeminiProvider:
        if self._fallback is None:
            self._fallback = GeminiProvider()
        return self._fallback

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_schema: dict,
        num_questions: int,
    ) -> dict:
        start = time.monotonic()

        try:
            result = await self._get_primary().generate_mcqs(
                system_prompt, user_prompt, tool_schema, num_questions
            )
            logger.info(f"Claude generation succeeded ({len(result['questions'])} questions)")
        except Exception as exc:
            logger.warning(f"Claude failed ({exc}), falling back to Gemini")
            result = await self._get_fallback().generate_mcqs(
                system_prompt, user_prompt, tool_schema, num_questions
            )
            logger.info(f"Gemini fallback succeeded ({len(result['questions'])} questions)")

        result["generation_time_ms"] = int((time.monotonic() - start) * 1000)
        return result

    async def modify_question(self, question: dict, modification_type: str, instruction: str) -> dict:
        """
        Send a single question + instruction to Claude for modification.
        Returns the modified question dict.
        """
        import json

        mod_type_instructions = {
            "REPHRASE": "Rephrase the question text and options using different wording. Keep the same answer.",
            "CHANGE_DIFFICULTY": f"Change the difficulty level as instructed: {instruction}",
            "CHANGE_OPTIONS": "Rewrite the distractor options to make them more plausible.",
            "REGENERATE": "Generate a completely new question on the same topic.",
            "CUSTOM": instruction or "Modify the question as appropriate.",
        }

        task = mod_type_instructions.get(modification_type, instruction)

        system = (
            "You are an expert educational assessment designer. "
            "You will receive a single MCQ question and a modification instruction. "
            "Return ONLY the modified question as a JSON object in exactly the same schema as the input. "
            "Do not add commentary."
        )
        user = (
            f"Modification instruction: {task}\n\n"
            f"Original question:\n{json.dumps(question, indent=2)}\n\n"
            "Return the modified question JSON."
        )

        try:
            import asyncio
            from anthropic import AnthropicVertex

            client = AnthropicVertex(
                region=settings.google_cloud_location_claude,
                project_id=settings.google_cloud_project,
            )

            def _call():
                return client.messages.create(
                    model=settings.claude_model,
                    max_tokens=2048,
                    temperature=0.4,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )

            response = await asyncio.get_event_loop().run_in_executor(None, _call)
            text = response.content[0].text.strip()

            # Strip code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            modified = json.loads(text)
            # Preserve original id if present
            if "id" in question and "id" not in modified:
                modified["id"] = question["id"]
            return modified

        except Exception as exc:
            logger.error(f"modify_question failed: {exc}")
            raise


# Singleton used by routers
mcq_service = MCQGenerationService()
