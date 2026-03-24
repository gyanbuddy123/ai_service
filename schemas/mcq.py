from typing import Any
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    session_id: str
    chapter_id: str
    subject: str = ""
    chapter: str = ""           # chapter title
    topic: str = ""             # sub-topic within chapter (optional)
    board: str = "CBSE"         # education board — hardcoded until board logic is implemented
    num_questions: int = Field(ge=1, le=50)
    grade_level: int = Field(ge=1, le=12, default=8)
    context_text: str = ""
    existing_question_stems: list[str] = []


class MCQOption(BaseModel):
    option_text: str
    is_correct: bool


class GeneratedQuestion(BaseModel):
    id: str
    question_text: str
    question_type: str = "mcq_single"
    options: list[MCQOption]
    difficulty_level: int
    explanation: str = ""
    hint: str = ""
    topic_tag: str = ""
    exp_points: int = 10
    question_order: int


class GenerateResponse(BaseModel):
    session_id: str
    questions: list[GeneratedQuestion]
    model_used: str
    generation_time_ms: int | None = None
    rejected_count: int = 0


class ModifyRequest(BaseModel):
    session_id: str
    question: dict[str, Any]    # the selected question as JSON
    modification_type: str = "CUSTOM"
    instruction: str = ""
    grade_level: int = Field(ge=1, le=12, default=8)
    subject: str = ""
    chapter: str = ""
    topic: str = ""
    board: str = "CBSE"         # education board — hardcoded until board logic is implemented


class ModifyResponse(BaseModel):
    session_id: str
    question: dict[str, Any]    # the modified question
