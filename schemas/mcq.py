from typing import Any
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    session_id: str
    chapter_id: str
    topic: str
    num_questions: int = Field(ge=1, le=50)
    grade_level: int = Field(ge=1, le=12, default=8)
    context_text: str = ""
    difficulty_distribution: dict[str, int] | None = None  # e.g. {"1": 2, "3": 5, "5": 3}


class MCQOption(BaseModel):
    key: str          # "A", "B", "C", "D"
    text: str


class GeneratedQuestion(BaseModel):
    id: str           # client-assigned, e.g. "q_<uuid>"
    question_text: str
    options: list[MCQOption]
    correct_answers: list[str]  # ["A"] or ["A", "C"]
    answer_type: str = "single"  # "single" | "multiple"
    hint: str = ""
    explanation: str = ""
    difficulty_level: int
    bloom_category: str = ""
    topic_tag: str = ""
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


class ModifyResponse(BaseModel):
    session_id: str
    question: dict[str, Any]    # the modified question
