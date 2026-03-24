"""
Build system and user prompts for MCQ generation.
"""
from __future__ import annotations


_BLOOM_MAPPING = """
Difficulty ↔ Bloom's Taxonomy mapping (follow strictly):
  Level 1 — REMEMBER: recall facts, definitions, dates
    Stems: "What is...", "Name the...", "Define...", "Which of the following is..."
  Level 2 — UNDERSTAND: explain concepts in own words
    Stems: "Which best describes...", "What does X mean...", "Why does X happen..."
  Level 3 — APPLY: use knowledge in new situations
    Stems: "If X occurs, what happens...", "Calculate...", "How would you use..."
  Level 4 — ANALYZE: break down, compare, contrast
    Stems: "What is the relationship between...", "Compare X and Y...", "Why is X different from Y..."
  Level 5 — EVALUATE / CREATE: judge, design, propose
    Stems: "Which solution is most appropriate...", "Justify...", "What would you recommend..."
"""

_HINT_RULES = """
Hint quality rules (ALL must be satisfied — no exceptions):
  1. Must guide the student's thinking process, not give away the answer.
  2. Must NEVER contain any word from the correct answer option text (after removing stop words).
  3. Must NEVER eliminate wrong options (do not hint "it is NOT A or B").
  4. Should reference a concept, principle, or process rather than the answer itself.
"""

_SELF_VERIFICATION = """
Self-verification (do this before calling submit_mcq_batch):
  For each question, verify:
  ✓ Every claim is supported by the provided chapter text
  ✓ Hint passes all hint rules above (no answer tokens)
  ✓ All distractors are plausible but clearly wrong to a knowledgeable student
  ✓ Bloom's category matches the stem pattern for the difficulty level
  ✓ No two questions test the same specific fact or concept
  If any check fails — fix the question before submitting.
"""


def build_system_prompt(grade_level: int, subject: str = "", chapter: str = "", board: str = "CBSE") -> str:
    if grade_level <= 5:
        grade_note = "Use concrete, simple language. Short sentences. No jargon."
    elif grade_level <= 8:
        grade_note = "Use moderate academic language. Some subject-specific vocabulary is fine."
    elif grade_level <= 10:
        grade_note = "Use academic language appropriate for secondary school students."
    else:
        grade_note = "Use college-preparatory academic language with full subject terminology."

    parts = [f"Board: {board}", f"Grade: {grade_level}"]
    if subject:
        parts.append(f"Subject: {subject}")
    if chapter:
        parts.append(f"Chapter: {chapter}")
    context_line = " | ".join(parts)

    return f"""You are an expert educational assessment designer specializing in Bloom's Taxonomy and Item Response Theory (IRT).

Your task: generate high-quality multiple-choice questions (MCQs) from the provided chapter content.

Curriculum context: {context_line}
Grade calibration: {grade_note}

{_BLOOM_MAPPING}

Difficulty distribution rules:
  • Assess the topic's breadth and cognitive depth before deciding the distribution.
  • A narrow, factual topic (e.g. definitions, dates) should lean toward levels 1–2.
  • A conceptual or applied topic should lean toward levels 3–4.
  • A complex, evaluative topic (e.g. analysis, design) should include levels 4–5.
  • For any n, choose a distribution that honestly reflects what the topic supports — do not force an even spread if the topic does not warrant it.
  • Avoid clustering all questions at one level unless the topic is genuinely limited in scope.

{_HINT_RULES}

{_SELF_VERIFICATION}

Output format: call the submit_mcq_batch tool with your questions. Do not output raw text."""


def build_user_prompt(
    chapter: str,
    num_questions: int,
    context_text: str,
    topic: str = "",
    existing_question_stems: list[str] | None = None,
) -> str:
    dedup_section = ""
    if existing_question_stems:
        stems_list = "\n".join(f"  - {s}" for s in existing_question_stems)
        dedup_section = f"\nAlready-asked questions (do NOT repeat these topics):\n{stems_list}\n"

    topic_line = f"\nTopic (sub-topic focus): {topic}" if topic else ""

    return f"""Chapter: {chapter}{topic_line}
Number of questions to generate: {num_questions}
{dedup_section}
Chapter content (use ONLY the information below to create questions):
---
{context_text[:12000]}
---

Generate exactly {num_questions} MCQ question(s) on the chapter above. Decide the difficulty distribution based on the topic's nature before generating. Call submit_mcq_batch when ready."""


SUBMIT_MCQ_BATCH_TOOL = {
    "name": "submit_mcq_batch",
    "description": "Submit the final validated batch of MCQ questions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "metadata": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "total_generated": {"type": "integer"},
                    "bloom_distribution": {
                        "type": "object",
                        "description": "Count per Bloom category, e.g. {REMEMBER: 2, UNDERSTAND: 3}",
                    },
                },
                "required": ["topic", "total_generated"],
            },
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_text": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "key": {"type": "string", "enum": ["A", "B", "C", "D"]},
                                    "text": {"type": "string"},
                                },
                                "required": ["key", "text"],
                            },
                            "minItems": 4,
                            "maxItems": 4,
                        },
                        "correct_answers": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["A", "B", "C", "D"]},
                            "minItems": 1,
                        },
                        "answer_type": {"type": "string", "enum": ["single", "multiple"]},
                        "hint": {"type": "string"},
                        "explanation": {"type": "string"},
                        "difficulty_level": {"type": "integer", "minimum": 1, "maximum": 5},
                        "bloom_category": {
                            "type": "string",
                            "enum": ["REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"],
                        },
                        "topic_tag": {"type": "string"},
                    },
                    "required": [
                        "question_text", "options", "correct_answers", "answer_type",
                        "hint", "explanation", "difficulty_level", "bloom_category",
                    ],
                },
            },
        },
        "required": ["metadata", "questions"],
    },
}
