from typing import Any
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    session_id: str
    chapter_id: str
    subject: str = ""
    chapter: str = ""           # chapter title
    topic: str = ""             # sub-topic within chapter (optional)
    board: str = "CBSE"         # education board
    num_questions: int = Field(ge=1, le=15)
    grade_level: int = Field(ge=1, le=12, default=8)
    context_text: str = ""
    existing_question_stems: list[str] = []


class MCQOption(BaseModel):
    option_text: str
    is_correct: bool
    correct_order: int | None = None  # Required for rearrange questions (1-based position)


class GeneratedQuestion(BaseModel):
    id: str
    question_text: str
    question_type: str = "mcq_single"
    options: list[MCQOption]
    difficulty_level: int
    explanation: str = ""
    hint: str = ""
    exp_points: int = 10
    question_order: int
    image_base64: str | None = None
    image_prompt: str | None = None


class GenerateResponse(BaseModel):
    session_id: str
    questions: list[GeneratedQuestion]
    generation_time_ms: int | None = None
    rejected_count: int = 0
    warning: str | None = None


class ModifyRequest(BaseModel):
    session_id: str
    question: dict[str, Any]    # the selected question as JSON
    modification_type: str = "CUSTOM"
    instruction: str = ""
    grade_level: int = Field(ge=1, le=12, default=8)
    subject: str = ""
    chapter: str = ""
    topic: str = ""
    board: str = "CBSE"
    chapter_id: str = ""        # for Qdrant context retrieval
    context_text: str = ""      # fallback if no Qdrant chunks


class ModifyResponse(BaseModel):
    session_id: str
    question: dict[str, Any]    # the modified question
