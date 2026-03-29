"""
Build system and user prompts for MCQ generation.
"""
from __future__ import annotations


_MOBILE_FORMAT_RULES = """
MOBILE DISPLAY RULES — strictly required (the app has NO LaTeX renderer):
  FORBIDDEN — never output:
    • LaTeX commands: \\frac{}{} \\sqrt{} \\int \\sum \\alpha \\beta \\pi \\times \\cdot \\sin \\cos \\log \\lim
    • Dollar delimiters: $...$ or $$...$$ or \\(...\\) or \\[...\\]
    • Caret for power: x^2 or x^{2}
    • Underscore for subscript: H_2O or x_{1}
    • Any backslash before a word: \\alpha, \\theta, \\Delta, etc.

  USE INSTEAD:
    Powers     : ⁰ ¹ ² ³ ⁴ ⁵  (e.g. x², cm², 10³)
    Subscripts : ₀ ₁ ₂ ₃ ₄  (e.g. H₂O, CO₂, x₁)
    Roots      : √ ∛  (e.g. √2, √(x+1))
    Fractions  : write as a/b  (e.g. 1/2, (x+1)/(x-1))
    Greek      : α β γ δ ε θ λ μ π σ φ ω Δ Σ Ω
    Operators  : × ÷ ± ≤ ≥ ≠ ≈ ∞ ∫ ∑ ∂
    Other      : ° · → ← ⇒ ∈ ∩ ∪

  This rule applies to ALL fields: question_text, option text, hint, explanation.
"""

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

_ANSWER_POSITION_RULES = """
Answer position rules:
  • Distribute the correct answer across positions A, B, C, D evenly across all questions.
  • Do NOT place the correct answer in the same position for more than 2 consecutive questions.
  • Vary the position intentionally — the pattern should not be predictable.
"""

_QUESTION_TYPE_RULES = """
Question type rules — choose the BEST type for each question based on the content:
  mcq_single   : Exactly ONE correct answer. Use for factual, conceptual, and analytical questions.
                 Provide exactly 4 options. Mark exactly one is_correct=true.

  mcq_multiple : TWO OR MORE correct answers. Use when the content has multiple valid aspects.
                 Provide exactly 4 options. Mark 2 or more as is_correct=true (can be all 4).
                 Question text MUST include "Select all that apply."

  rearrange    : Student arranges items in the correct sequence or order.
                 Use for processes, steps, timelines, or logical sequences.
                 Provide 4–6 items. ALL options must have is_correct=true.
                 Each option MUST have correct_order (1-based integer for its position in correct sequence).
                 Return options in SCRAMBLED order — NOT in the correct sequence.
                 Question text MUST ask the student to arrange/order the items.
"""

_IMAGE_RULES = """
Image/diagram rules (only when generating diagram-based questions):
  • Provide a matplotlib_code field with Python code using ONLY plt and np (no other imports).
  • The figure must show the PROBLEM SETUP only — never the answer.
  • CRITICAL — the image must NOT reveal the answer:
      - If the question asks "calculate angle X", the image must show the triangle/shape with
        angle X marked as unknown (e.g. labelled "?") — never show the numerical value of X.
      - If the question asks "find the missing side", show the side as unknown — never its length.
      - If the question asks about a process outcome, show only the initial state — never the result.
  • FORBIDDEN in the code: plt.title(), ax.set_title(), plt.text() or ax.text() that show the
    answer value, ax.annotate() revealing the answer, plt.figtext(), plt.savefig(), plt.show().
  • ALLOWED: vertex labels (single letters A, B, C), axis labels with units, shapes, curves,
    given values that are part of the problem statement (not the answer), "?" label for unknowns.
  • The code must be complete and runnable with just plt and np available.
  • Only add a diagram when it genuinely helps the student understand the question setup.
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

{_MOBILE_FORMAT_RULES}
{_BLOOM_MAPPING}

Difficulty distribution rules:
  • Assess the topic's breadth and cognitive depth before deciding the distribution.
  • A narrow, factual topic (e.g. definitions, dates) should lean toward levels 1–2.
  • A conceptual or applied topic should lean toward levels 3–4.
  • A complex, evaluative topic (e.g. analysis, design) should include levels 4–5.
  • For any n, choose a distribution that honestly reflects what the topic supports — do not force an even spread if the topic does not warrant it.
  • Avoid clustering all questions at one level unless the topic is genuinely limited in scope.

{_QUESTION_TYPE_RULES}

{_ANSWER_POSITION_RULES}

{_HINT_RULES}

{_IMAGE_RULES}

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
{context_text}
---

Generate exactly {num_questions} MCQ question(s) focused strictly on the topic "{topic}" using only the content provided above. Mix question types (mcq_single, mcq_multiple, rearrange) where appropriate based on the content. Where a diagram genuinely aids a question, include matplotlib_code. Decide the difficulty distribution based on the topic's nature before generating. Call submit_mcq_batch when ready."""


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
                        "question_type": {
                            "type": "string",
                            "enum": ["mcq_single", "mcq_multiple", "rearrange"],
                        },
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "option_text": {"type": "string"},
                                    "is_correct": {"type": "boolean"},
                                    "correct_order": {
                                        "type": "integer",
                                        "description": "1-based position in correct sequence. Required for rearrange type.",
                                    },
                                },
                                "required": ["option_text", "is_correct"],
                            },
                            "minItems": 4,
                            "maxItems": 6,
                        },
                        "hint": {"type": "string"},
                        "explanation": {"type": "string"},
                        "difficulty_level": {"type": "integer", "minimum": 1, "maximum": 5},
                        "matplotlib_code": {
                            "type": "string",
                            "description": "Optional matplotlib Python code to draw the problem setup diagram. Must NOT reveal the answer value.",
                        },
                    },
                    "required": [
                        "question_text", "question_type", "options",
                        "hint", "explanation", "difficulty_level",
                    ],
                },
            },
        },
        "required": ["metadata", "questions"],
    },
}
