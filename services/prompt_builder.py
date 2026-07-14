"""
Build system and user prompts for MCQ generation and modification.
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

_SOURCE_INDEPENDENCE_RULES = """
Source-independence rules — CRITICAL (applies to ALL fields: question_text, options, hint, explanation):
  Questions and explanations must read as STANDALONE educational content.
  The student must NEVER know that a PDF, textbook, or passage was involved.

  FORBIDDEN phrases (any variation of these):
    • "the text mentions / states / provides / says / explicitly states"
    • "in activity X.X", "in section X.X", "in exercise X.X"
    • "table X.X shows / clearly states / indicates"
    • "the table shows", "consult the table", "refer to the table"
    • "the passage states", "according to the passage"
    • "as mentioned in the chapter", "the chapter states"
    • "as given in the text", "as described above", "the above text"
    • Any numbered activity, figure, table, or exercise reference (e.g. "Activity 9.2", "Fig. 3.1")

  INSTEAD — write the fact, concept, or data directly into the question or explanation:
    ✗ "The text states that photosynthesis occurs in the chloroplast."
    ✓ "Photosynthesis occurs in the chloroplast."
    ✗ "Table 9.1 shows the boiling points of these liquids."
    ✓ "The boiling points of these liquids are: water — 100°C, ethanol — 78°C."
    ✗ "As mentioned in Activity 9.2, the solution turns blue."
    ✓ "When starch is present, iodine solution turns blue."
"""

_HINT_RULES = """
Hint quality rules (ALL must be satisfied — no exceptions):
  1. Must guide the student's thinking process, not give away the answer.
  2. Must NEVER contain any word from the correct answer option text (after removing stop words).
  3. Must NEVER eliminate wrong options (do not hint "it is NOT A or B").
  4. Should reference a concept, principle, or process rather than the answer itself.
  5. Must be FULLY SELF-CONTAINED — strictly forbidden to reference:
       • Theorem, Lemma, Corollary, Property, or Rule by number (e.g. "Theorem 6.6", "Rule 2.1")
       • Textbook pages, chapters, sections, figures, tables, or activities by number
       • Phrases like "Refer to...", "See page...", "As stated in...", "According to Theorem...",
         "the text says...", "as mentioned in the chapter..."
     Instead, state the underlying principle or key idea directly in the hint text.
     A student with no textbook must be able to use this hint.
"""

_EXPLANATION_RULES = """
Explanation quality rules (ALL must be satisfied — no exceptions):
  1. Must be concise — MAXIMUM 300 characters. Stay well within this limit.
  2. Must clearly justify WHY the correct answer is right and WHY each distractor is wrong.
  3. Must be FULLY SELF-CONTAINED — strictly forbidden to reference:
       • Theorem, Lemma, Corollary, Property, or Rule by number (e.g. "Theorem 6.6")
       • Textbook pages, chapters, sections, figures, tables, or activities by number
       • Phrases like "Refer to...", "See page...", "As stated in...", "According to Theorem...",
         "the text states...", "as shown in the table...", "Activity X.X shows..."
     Instead, explain the reasoning and logic inline — embed any needed facts directly.
  4. Must use the same mobile-safe formatting rules as all other fields (no LaTeX).
"""

_SELF_VERIFICATION = """
Self-verification (do this before submitting):
  For each question, verify:
  ✓ Every claim is supported by the provided chapter text
  ✓ question_text contains NO reference to the source material (no "the text", "activity X", "table X")
  ✓ hint contains NO reference to the source material, theorem numbers, or page references
  ✓ explanation contains NO reference to the source material, theorem numbers, or page references
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

_COMPETENCY_DIFFICULTY_RULES = """
Difficulty rules for Competency Assessment (STRICT — no exceptions):
  • Generate ONLY difficulty levels 4 and 5. Levels 1, 2, and 3 are FORBIDDEN.
  • Level 4 — ANALYZE: break down, compare, contrast relationships within the chapter.
    Stems: "What is the relationship between...", "Compare...", "Why is X different from Y..."
  • Level 5 — EVALUATE / CREATE: judge, design, propose, justify using chapter knowledge.
    Stems: "Which solution is most appropriate...", "Justify...", "What would you recommend...", "Design..."
  • Every question must require the student to go beyond recall — analysis or evaluation only.
  • Do NOT generate any question that can be answered by simple recall or recognition.
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
                 Return options in correct sequence order (sorted by correct_order ascending).
                 Question text MUST ask the student to arrange/order the items.
                 CRITICAL — option_text for each item must describe the step/event/stage directly.
                 NEVER use labels like "Activity 1.1", "Step 2.3", "Section 4", "Fig. 1.1", or any
                 numbered reference as the item text. Write the actual content of the step instead.
"""

_DIFFICULTY_DISTRIBUTION_RULES = """
Difficulty distribution rules:
  • Assess the topic's breadth and cognitive depth before deciding the distribution.
  • A narrow, factual topic (e.g. definitions, dates) should lean toward levels 1–2.
  • A conceptual or applied topic should lean toward levels 3–4.
  • A complex, evaluative topic (e.g. analysis, design) should include levels 4–5.
  • For any n, choose a distribution that honestly reflects what the topic supports — do not force an even spread if the topic does not warrant it.
  • Avoid clustering all questions at one level unless the topic is genuinely limited in scope.
"""

_IMAGE_RULES = """
Image/diagram rules (only when a visual genuinely helps the student understand the question):
  • Set the image_prompt field to a clear 2–3 sentence description of what to show.
  • Works for ANY subject — geometry, physics, biology, chemistry, history maps, etc.
  • The image must show the PROBLEM SETUP only — NEVER the answer.
  • CRITICAL — the description must NOT imply or include the answer:
      - If the question asks "what is angle X?", describe the shape with angle X marked as "?".
      - If the question asks about a process outcome, describe only the initial state.
      - If the question asks to identify a structure, show the structure with the target part unlabelled.
  • Include all relevant labels, measurements, and given values that are part of the problem.
  • Example: "A bar magnet with S on the left and N on the right. Magnetic field lines curve from
    N to S outside the magnet. The direction of field lines inside the magnet is marked with '?'."
  • Only add an image when it genuinely aids comprehension — do not add one for purely text-based questions.
"""


# ── Shared per-question JSON schema — single source of truth for generate + modify ──────────────

QUESTION_ITEM_SCHEMA = {
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
        "image_prompt": {
            "type": "string",
            "description": (
                "Optional. A concise 2-3 sentence description of a diagram to show with this question. "
                "Describe ONLY the problem setup — never include or imply the answer. "
                "Works for any subject (geometry, biology, chemistry, physics, etc.)."
            ),
        },
    },
    "required": [
        "question_text", "question_type", "options",
        "hint", "explanation", "difficulty_level",
    ],
}

# Task descriptions for each predefined modification type.
# CUSTOM is intentionally absent — it uses the user's instruction directly.
MODIFY_TYPE_TASKS = {
    "REPHRASE": "Rephrase the question text and options using different wording. Keep the same correct answer.",
    "INCREASE_DIFFICULTY": "Increase the difficulty level by one step. Deepen the cognitive demand (e.g. from recall to application). Update difficulty_level accordingly.",
    "DECREASE_DIFFICULTY": "Decrease the difficulty level by one step. Simplify the cognitive demand. Update difficulty_level accordingly.",
    "CHANGE_OPTIONS": "Rewrite the distractor options to make them more plausible and challenging, without changing the correct answer.",
    "REGENERATE": "Generate a completely new question on the same topic and difficulty level.",
}


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

You create and refine high-quality multiple-choice questions (MCQs) for educational content.

Curriculum context: {context_line}
Grade calibration: {grade_note}

{_MOBILE_FORMAT_RULES}

{_SOURCE_INDEPENDENCE_RULES}

{_BLOOM_MAPPING}

{_DIFFICULTY_DISTRIBUTION_RULES}

{_QUESTION_TYPE_RULES}

{_ANSWER_POSITION_RULES}

{_HINT_RULES}

{_EXPLANATION_RULES}

{_IMAGE_RULES}

{_SELF_VERIFICATION}

Output format: return your response as structured JSON matching the provided schema. No markdown, no code fences, no plain text."""


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

Generate exactly {num_questions} MCQ question(s) focused strictly on the topic "{topic}" using only the content provided above. Mix question types (mcq_single, mcq_multiple, rearrange) where appropriate. Where a diagram genuinely aids a question, set image_prompt to a clear description of what to show. Decide the difficulty distribution based on the topic's nature before generating. Return all questions as a JSON array."""


def build_prereq_system_prompt(grade_level: int, subject: str = "", chapter: str = "", board: str = "CBSE") -> str:
    prereq_grade = max(1, grade_level - 1)

    if prereq_grade <= 5:
        grade_note = "Use concrete, simple language. Short sentences. No jargon."
    elif prereq_grade <= 8:
        grade_note = "Use moderate academic language. Some subject-specific vocabulary is fine."
    elif prereq_grade <= 10:
        grade_note = "Use academic language appropriate for secondary school students."
    else:
        grade_note = "Use college-preparatory academic language with full subject terminology."

    parts = [f"Board: {board}", f"Current Grade: {grade_level}", f"Prerequisite Grade: {prereq_grade}"]
    if subject:
        parts.append(f"Subject: {subject}")
    if chapter:
        parts.append(f"Chapter: {chapter}")
    context_line = " | ".join(parts)

    return f"""You are an expert educational assessment designer specialising in prerequisite and foundational knowledge assessment.

Your task is to generate MCQs that check whether a Class {grade_level} student has the foundational knowledge from Class {prereq_grade} needed to successfully study this chapter.

Curriculum context: {context_line}
Grade calibration (target prerequisite level — Class {prereq_grade}): {grade_note}

You do NOT have a textbook excerpt for this task. Use your knowledge of the {board} curriculum to identify:
  • Concepts and skills taught at Class {prereq_grade} level for this chapter's topic
  • Foundational understanding a student must have before advancing to Class {grade_level} content
  • Common prerequisite gaps that cause students to struggle with this chapter

Questions must be pitched at Class {prereq_grade} difficulty — not the current Class {grade_level} level.

{_MOBILE_FORMAT_RULES}

{_SOURCE_INDEPENDENCE_RULES}

{_BLOOM_MAPPING}

{_DIFFICULTY_DISTRIBUTION_RULES}

{_QUESTION_TYPE_RULES}

{_ANSWER_POSITION_RULES}

{_HINT_RULES}

{_EXPLANATION_RULES}

{_IMAGE_RULES}

{_SELF_VERIFICATION}

Output format: return your response as structured JSON matching the provided schema. No markdown, no code fences, no plain text."""


def build_prereq_user_prompt(
    chapter: str,
    num_questions: int,
    board: str = "CBSE",
    grade_level: int = 8,
    existing_question_stems: list[str] | None = None,
) -> str:
    prereq_grade = max(1, grade_level - 1)

    dedup_section = ""
    if existing_question_stems:
        stems_list = "\n".join(f"  - {s}" for s in existing_question_stems)
        dedup_section = f"\nAlready-asked questions (do NOT repeat these topics):\n{stems_list}\n"

    return f"""Chapter: {chapter}
Topic: Previous Knowledge Testing
Current Grade: {grade_level} | Prerequisite grade to assess: {prereq_grade}
Number of questions to generate: {num_questions}
{dedup_section}
Generate exactly {num_questions} MCQ question(s) that test the foundational knowledge a Class {grade_level} student should already have from Class {prereq_grade} before studying "{chapter}". Use your knowledge of the {board} curriculum to determine what prerequisite concepts are expected at Class {prereq_grade} level. Questions must be pitched at Class {prereq_grade} difficulty — not the current Class {grade_level} level. Mix question types (mcq_single, mcq_multiple, rearrange) where appropriate. Where a diagram genuinely aids a question, set image_prompt to a clear description of what to show. Return all questions as a JSON array."""


def build_competency_system_prompt(grade_level: int, subject: str = "", chapter: str = "", board: str = "CBSE") -> str:
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

    return f"""You are an expert educational assessment designer specialising in higher-order thinking and competency-based assessment.

Your task is to generate advanced MCQs that assess a student's deep understanding and analytical ability across the ENTIRE chapter — not recall of specific facts.

Curriculum context: {context_line}
Grade calibration: {grade_note}

{_MOBILE_FORMAT_RULES}

{_SOURCE_INDEPENDENCE_RULES}

{_BLOOM_MAPPING}

{_COMPETENCY_DIFFICULTY_RULES}

{_QUESTION_TYPE_RULES}

{_ANSWER_POSITION_RULES}

{_HINT_RULES}

{_EXPLANATION_RULES}

{_IMAGE_RULES}

{_SELF_VERIFICATION}

Output format: return your response as structured JSON matching the provided schema. No markdown, no code fences, no plain text."""


def build_competency_user_prompt(
    chapter: str,
    num_questions: int,
    context_text: str,
    existing_question_stems: list[str] | None = None,
) -> str:
    dedup_section = ""
    if existing_question_stems:
        stems_list = "\n".join(f"  - {s}" for s in existing_question_stems)
        dedup_section = f"\nAlready-asked questions (do NOT repeat these topics):\n{stems_list}\n"

    return f"""Chapter: {chapter}
Assessment Type: Competency Assessment (whole chapter, levels 4–5 only)
Number of questions to generate: {num_questions}
{dedup_section}
Chapter content (use ONLY the information below to create questions):
---
{context_text}
---

Generate exactly {num_questions} higher-order MCQ question(s) covering the FULL breadth of this chapter. Every question must be difficulty level 4 (Analyze) or 5 (Evaluate/Create) — do NOT generate any level 1, 2, or 3 questions. Questions must require the student to analyse relationships, evaluate arguments, or apply concepts in novel ways — not recall facts. Mix question types (mcq_single, mcq_multiple, rearrange) where appropriate. Return all questions as a JSON array."""


_COMPREHENSION_PASSAGE_RULES = """
Comprehension passage rules — this is a reading comprehension assessment:

  PASSAGE EMBEDDING (CRITICAL — no exceptions):
  • Every question_text MUST begin with the FULL passage, formatted exactly like this:

      Read the following passage carefully:

      [full passage text here — same passage, word for word, in every question]

      ──────────────────────────────────────

      [Actual question stem here]

  • The separator line (──────────────────────────────────────) MUST appear between the passage and the question stem in every question — this helps the display layer distinguish passage from question without any extra logic.
  • The passage must appear identically in ALL questions — do NOT shorten, summarise, or alter it.
  • The actual question stem comes AFTER the separator line.

  PASSAGE QUALITY:
  • The passage must be approximately 200 words — not shorter, not significantly longer.
  • Write in clear, flowing prose appropriate for the grade level.
  • The passage must be self-contained and interesting — a short story, biography excerpt,
    nature description, historical anecdote, or informational paragraph.

  QUESTION COVERAGE — cover a balanced mix across the question set:
      - Specific detail       : facts directly stated in the passage
      - Inference             : conclusions drawn from implied or unstated meaning
      - Vocabulary in context : meaning of a word/phrase as used in the passage
      - Main idea / theme     : what the passage is primarily about
      - Tone / mood / author's purpose : the writer's attitude or intent
      - Title suggestion      : best title that captures the passage's central theme
      - Complete the sentence : fill-in-the-blank using mcq_single — put ___ in the
                                question stem and provide 4 word/phrase options
                                e.g. "The old man was known for his ___."

  • Questions SHOULD naturally reference the passage:
      "According to the passage...", "The passage suggests...", "In the context of the passage..."
  • Do NOT ask questions that can be answered without reading the passage.
  • Do NOT test grammar rules or language conventions — focus only on comprehension.
"""

_COMPREHENSION_SELF_VERIFICATION = """
Self-verification (do this before submitting):
  For each question, verify:
  ✓ question_text starts with "Read the following passage carefully:" followed by the FULL passage
  ✓ The full passage (~200 words) is embedded identically in every question_text
  ✓ The actual question stem appears AFTER the passage
  ✓ The answer can be found in or clearly inferred from the passage
  ✓ hint guides thinking without giving away the answer
  ✓ explanation cites the relevant part of the passage that justifies the answer
  ✓ All distractors are plausible but clearly wrong to a careful reader
  ✓ No two questions test the exact same sentence or detail
  If any check fails — fix the question before submitting.
"""


_GRAMMAR_RULES = """
Grammar assessment rules — this is an English grammar assessment:
  • Questions must test practical grammar knowledge using example sentences.
  • Cover a mix of grammar skills appropriate for the grade level:
      - Fill in the blank   : choose the correct word/form to complete a sentence
      - Error detection     : identify the grammatically incorrect part of a sentence
      - Correct form        : choose the right tense, article, preposition, or conjunction
      - Sentence correction : select the correctly written version of a sentence
      - Parts of speech     : identify nouns, verbs, adjectives, adverbs, etc.
      - Voice / Speech      : active/passive voice or direct/indirect speech transformation
  • Every question must include a clear example sentence or context.
  • Distractors must be grammatically plausible — common errors students actually make.
  • Do NOT ask theoretical definitions ("What is a noun?") — test application only.
  • Do NOT reference any textbook, chapter, or external source.
"""

_GRAMMAR_ADVANCED_RULES = """
Advanced grammar question types — REQUIRED for Class 9 and 10 (mix these into the question set):

  1. EDIT (Error Editing):
     • Show a sentence containing ONE grammatical error (tense, modal, subject-verb agreement, etc.).
     • Use mcq_single. Ask the student to identify the error and its correction.
     • Format: "Identify the error and its correction: 'She go to school every day.'"
     • Options: A) go → goes  B) go → went  C) go → going  D) No error
     • Exactly one option gives the correct word + its replacement.

  2. OMISSIONS:
     • Show a sentence or short paragraph with ONE word omitted, marked by /\\ or a blank ___.
     • Use mcq_single. Student selects the missing word/phrase that best fills the gap.
     • Format: "Fill in the missing word: 'He was tired ___ he kept working.'"
     • Options: four grammatically plausible words/phrases, only one correct.

  3. REPORTED SPEECH:
     • Give a direct speech sentence and ask for the correct indirect (reported) form, or vice versa.
     • Use mcq_single.
     • Format: "Change to reported speech: Ram said, 'I am very hungry.'"
     • Options: four reported speech versions with subtle tense/pronoun differences.
     • Only one option correctly applies all reported speech transformation rules.

  4. SENTENCE REORDERING:
     • Give jumbled words or sentence parts that must be arranged into a correct, meaningful sentence.
     • Use rearrange question type. Each option is one word or phrase segment.
     • All options must have is_correct=true with correct_order assigned (1-based).
     • Format: question_text asks the student to arrange the given words/phrases into a sentence.
"""

_GRAMMAR_SELF_VERIFICATION = """
Self-verification (do this before submitting):
  For each question, verify:
  ✓ The question tests grammar application, not rote definition recall
  ✓ The example sentence is clear and unambiguous
  ✓ Exactly one option is grammatically correct (for mcq_single)
  ✓ Distractors reflect real grammar mistakes students make
  ✓ hint points to the grammar rule without giving away the answer
  ✓ explanation names the grammar rule and explains why the correct option applies
  ✓ No two questions test the exact same rule in the exact same way
  If any check fails — fix the question before submitting.
"""


def _grammar_grade_curriculum(grade_level: int) -> str:
    if grade_level <= 2:
        return """Grade 1–2 grammar scope:
  Topics   : Common nouns, pronouns (I/we/he/she/they), simple present tense, articles (a/an),
              capital letters, full stops, question marks, simple positive sentences.
  Formats  : Fill in the blank, choose the correct word (2–4 simple options).
  Sentences: Very short (5–8 words), everyday vocabulary only.
  Avoid    : Multi-clause sentences, modals, passive voice, tenses other than simple present."""
    elif grade_level <= 4:
        return """Grade 3–4 grammar scope:
  Topics   : Common & proper nouns, pronouns, simple present/past/future tense, articles (a/an/the),
              basic adjectives, simple prepositions (in/on/at/under), conjunctions (and/but/or).
  Formats  : Fill in the blank, choose the correct form, sentence correction (single error).
  Sentences: Short to medium (8–12 words), familiar vocabulary.
  Avoid    : Perfect tenses, passive voice, reported speech, modals."""
    elif grade_level == 5:
        return """Grade 5 grammar scope:
  Topics   : All basic tenses (simple present/past/future), articles, adjectives (degrees of comparison),
              adverbs, prepositions, conjunctions, negatives, question formation, subject-verb agreement.
  Formats  : Fill in the blank, choose the correct form, error spotting, sentence correction.
  Sentences: Medium length (10–15 words), school-level vocabulary.
  Avoid    : Perfect continuous tenses, passive voice, reported speech, complex modals."""
    elif grade_level <= 7:
        return """Grade 6–7 grammar scope:
  Topics   : All simple + continuous tenses, perfect tenses (introduction), modals (can/could/may/might/will/would/shall/should),
              active/passive voice (simple cases), degrees of comparison, conjunctions, prepositions,
              subject-verb agreement, basic reported speech (statements only).
  Formats  : Fill in the blank, choose the correct form/tense/modal, error spotting,
              sentence correction, active ↔ passive transformation (simple cases).
  Sentences: Medium to complex (12–18 words), age-appropriate vocabulary.
  Avoid    : Perfect continuous passive, advanced conditional sentences."""
    elif grade_level == 8:
        return """Grade 8 grammar scope:
  Topics   : All tenses including perfect continuous, all modals, active/passive voice (all tenses),
              direct/indirect speech (statements, questions, commands), conditional sentences (type 1 & 2),
              phrases and clauses, degrees of comparison, relative pronouns.
  Formats  : Fill in the blank, choose the correct form, error spotting, sentence correction,
              active ↔ passive transformation, direct ↔ indirect speech conversion.
  Sentences: Complex (15–20 words), varied vocabulary appropriate for Class 8.
  Avoid    : Type 3 conditionals, mixed conditionals, advanced stylistic questions."""
    else:
        return ""  # Grade 9-10 handled by _GRAMMAR_ADVANCED_RULES


def build_grammar_system_prompt(grade_level: int, subject: str = "", chapter: str = "", board: str = "CBSE") -> str:
    if grade_level <= 2:
        grade_note = "Use very simple, everyday language. Sentences must be short. No jargon."
    elif grade_level <= 4:
        grade_note = "Use simple language with familiar vocabulary. Sentences should be short to medium."
    elif grade_level <= 6:
        grade_note = "Use clear, school-level language. Moderate sentence complexity."
    elif grade_level <= 8:
        grade_note = "Use moderately complex sentences with age-appropriate vocabulary."
    elif grade_level <= 10:
        grade_note = "Use complex sentences with full secondary-school grammar range."
    else:
        grade_note = "Use advanced grammar with nuanced usage and stylistic correctness."

    parts = [f"Board: {board}", f"Grade: {grade_level}"]
    if subject:
        parts.append(f"Subject: {subject}")
    if chapter:
        parts.append(f"Chapter: {chapter}")
    context_line = " | ".join(parts)

    grade_curriculum = _grammar_grade_curriculum(grade_level)
    advanced_rules = _GRAMMAR_ADVANCED_RULES if grade_level in (9, 10) else ""

    return f"""You are an expert English grammar assessment designer with deep knowledge of the {board} curriculum.

Your task is to generate MCQs that test a student's practical understanding and application of English grammar rules.

Curriculum context: {context_line}
Grade calibration: {grade_note}

{grade_curriculum}
{_MOBILE_FORMAT_RULES}

{_GRAMMAR_RULES}
{advanced_rules}
{_BLOOM_MAPPING}

{_DIFFICULTY_DISTRIBUTION_RULES}

{_QUESTION_TYPE_RULES}

{_ANSWER_POSITION_RULES}

{_HINT_RULES}

{_EXPLANATION_RULES}

{_GRAMMAR_SELF_VERIFICATION}

Output format: return your response as structured JSON matching the provided schema. No markdown, no code fences, no plain text."""


def build_grammar_user_prompt(
    chapter: str,
    num_questions: int,
    board: str = "CBSE",
    grade_level: int = 8,
    topic: str = "",
    existing_question_stems: list[str] | None = None,
) -> str:
    dedup_section = ""
    if existing_question_stems:
        stems_list = "\n".join(f"  - {s}" for s in existing_question_stems)
        dedup_section = f"\nAlready-asked questions (do NOT repeat these):\n{stems_list}\n"

    topic_line = f"\nGrammar Topic (focus on this): {topic}" if topic else ""

    return f"""Chapter: {chapter}
Assessment Type: English Grammar
Board: {board} | Grade: {grade_level}{topic_line}
Number of questions to generate: {num_questions}
{dedup_section}
Generate exactly {num_questions} grammar MCQ question(s) based on your knowledge of the {board} Class {grade_level} English grammar curriculum. Use a mix of question formats: fill in the blank, error detection, correct form selection, sentence correction. Every question must include a clear example sentence. Do not ask for definitions — test application only. Mix question types (mcq_single, mcq_multiple) where appropriate. Return all questions as a JSON array."""


def build_comprehension_system_prompt(grade_level: int, subject: str = "", chapter: str = "", board: str = "CBSE") -> str:
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

    return f"""You are an expert educational assessment designer specialising in English reading comprehension.

Your task is to generate MCQs that test a student's ability to read and understand a given passage.

Curriculum context: {context_line}
Grade calibration: {grade_note}

{_MOBILE_FORMAT_RULES}

{_COMPREHENSION_PASSAGE_RULES}

{_BLOOM_MAPPING}

{_DIFFICULTY_DISTRIBUTION_RULES}

{_QUESTION_TYPE_RULES}

{_ANSWER_POSITION_RULES}

{_HINT_RULES}

{_EXPLANATION_RULES}

{_COMPREHENSION_SELF_VERIFICATION}

Output format: return your response as structured JSON matching the provided schema. No markdown, no code fences, no plain text."""


def build_comprehension_user_prompt(
    chapter: str,
    num_questions: int,
    board: str = "CBSE",
    grade_level: int = 8,
    existing_question_stems: list[str] | None = None,
) -> str:
    dedup_section = ""
    if existing_question_stems:
        stems_list = "\n".join(f"  - {s}" for s in existing_question_stems)
        dedup_section = f"\nAlready-asked questions (do NOT repeat these):\n{stems_list}\n"

    return f"""Chapter: {chapter}
Assessment Type: Comprehension Passage
Board: {board} | Grade: {grade_level}
Number of questions to generate: {num_questions}
{dedup_section}
STEP 1 — Write a passage:
  • Compose an original passage of approximately 200 words suitable for a Class {grade_level} {board} student.
  • The passage should relate to the theme or topic of "{chapter}" where possible.
  • It may be a short story, biographical excerpt, nature description, historical anecdote, or informational paragraph.
  • The passage must be engaging, self-contained, and written in clear prose.

STEP 2 — Generate questions from that passage:
  Generate exactly {num_questions} MCQ question(s) based strictly on the passage you wrote.

CRITICAL — question_text format for EVERY question:
  Read the following passage carefully:

  [your full ~200-word passage — identical word for word in every question]

  ──────────────────────────────────────

  [question stem]

Cover a mix of comprehension skills: specific detail, inference, vocabulary in context, main idea, tone/author's purpose. Use mcq_single for most questions; use mcq_multiple only when multiple aspects are genuinely correct. Do not use rearrange type. Return all questions as a JSON array."""


def build_batch_fix_prompt(items: list[dict]) -> str:
    """
    Build a prompt to fix all rejected questions in a single LLM call.

    items: list of {index, fix_instruction, question}
    """
    import json
    return (
        "You will receive a list of MCQ questions that each have a specific issue. "
        "Fix each question according to its individual fix_instruction. "
        "Apply ONLY the specified fix — do not change anything else. "
        "Return a JSON object with a 'questions' array containing the fixed questions "
        "in the same order as the input (same length).\n\n"
        f"Questions to fix:\n{json.dumps(items, indent=2)}"
    )


# Modify prompts only need enough context to verify one question's correctness —
# not the entire chapter. Keep this small to avoid Gemini JSON truncation with
# guided generation (response_schema + large input causes incomplete output).
_MODIFY_CONTEXT_LIMIT = 3000


def build_modify_user_prompt(
    question: dict,
    modification_type: str,
    instruction: str,
    context_text: str = "",
) -> str:
    import json

    # CUSTOM: use the user's instruction directly.
    # All predefined types: use the task description from MODIFY_TYPE_TASKS.
    if modification_type == "CUSTOM":
        task = instruction or "Improve the question quality."
    else:
        task = MODIFY_TYPE_TASKS.get(modification_type, modification_type)

    context_section = ""
    if context_text:
        truncated = context_text[:_MODIFY_CONTEXT_LIMIT]
        if len(context_text) > _MODIFY_CONTEXT_LIMIT:
            truncated += "\n[...content truncated for brevity...]"
        context_section = (
            f"\n\nChapter content (verify correctness against this):\n---\n{truncated}\n---"
        )

    original_type = question.get("question_type", "mcq_single")

    _TYPE_RULES = {
        "mcq_single": (
            "question_type MUST be \"mcq_single\". "
            "Provide EXACTLY 4 options. "
            "EXACTLY 1 option must have is_correct=true. All others must have is_correct=false. "
            "Do NOT make all options correct. Do NOT add correct_order to any option."
        ),
        "mcq_multiple": (
            "question_type MUST be \"mcq_multiple\". "
            "Provide EXACTLY 4 options. "
            "2 OR MORE options must have is_correct=true. "
            "Question text MUST include 'Select all that apply.' "
            "Do NOT add correct_order to any option."
        ),
        "rearrange": (
            "question_type MUST be \"rearrange\". "
            "Provide 4 to 6 options. "
            "ALL options must have is_correct=true. "
            "EVERY option MUST have a correct_order integer (1-based, unique, contiguous from 1 to N). "
            "Return options sorted by correct_order ascending. "
            "Question text MUST ask the student to arrange or order the items."
        ),
    }
    type_rule = _TYPE_RULES.get(original_type, _TYPE_RULES["mcq_single"])

    return (
        f"Modification task: {task}\n\n"
        f"Original question:\n{json.dumps(question, indent=2)}"
        f"{context_section}\n\n"
        f"STRUCTURAL RULES — you MUST follow these exactly (no exceptions):\n"
        f"  • {type_rule}\n"
        f"  • Do NOT change question_type — it must remain \"{original_type}\".\n"
        f"  • Do NOT change difficulty_level unless the task explicitly requires it.\n"
        "Apply ONLY the modification described above. Return the updated question as a JSON object."
    )


# ── Lab Manual / Science Experiment prompts ───────────────────────────────────

_LAB_MANUAL_IMAGE_RULES = """
Lab manual image rules — MANDATORY (not optional like general questions):

  For lab manual / science experiment questions, set image_prompt on EXACTLY 2 or 3 questions total — no more.
  Choose the questions where a diagram adds the most educational value. Priority order:
  REQUIRED (pick 2–3 from these question types, then stop):
    1. Apparatus / Setup questions — show the experimental setup or arrangement of equipment.
         image_prompt example: "A diagram showing [apparatus names] arranged as in the experiment.
         Label each component. Leave the [specific part being asked about] unlabelled or marked '?'."

    2. Observation / Graph questions — show a graph or data table from the experiment.
         image_prompt example: "A graph with [X-axis label] on the horizontal axis and
         [Y-axis label] on the vertical axis. Plot the data points from the experiment.
         The graph shows a [linear/curved/etc.] relationship. The slope or specific point
         being asked about is marked with '?'."

    3. In-lab scenario with a visible setup — show the experiment in progress at the step
       described in the question.
         image_prompt example: "A student is performing [specific step of the experiment].
         Show the apparatus in the state described: [specific details of what is visible].
         Label all components. Do NOT show the result or answer."

    4. Safety / Hazard questions — show a lab scene where the safety concern is visible.
         image_prompt example: "A lab bench with [apparatus]. Show [the hazard situation
         being described]. Do NOT label or mark the correct safety action."

  OPTIONAL (set image_prompt only if a diagram genuinely adds value):
    - Aim/purpose questions (usually no image needed)
    - Theory/formula questions (add image if a diagram of the concept helps)
    - Conclusion questions (add image if showing the final result graph helps)
    - Rearrange / procedure ordering (no image needed — the steps ARE the question)

  Image quality rules (same as always):
    • Show ONLY the problem setup — NEVER the answer
    • Label all components except the one being asked about (mark it '?' instead)
    • White background, clean educational diagram style
    • For science experiments: use clear line-art style with component labels
"""

_LAB_MANUAL_RULES = """
Lab manual assessment rules — this is a science experiment assessment:

  CORE PRINCIPLE: At least 50% of questions MUST use IN-LAB SCENARIO framing — put the student
  physically inside the experiment. The student should feel they are reading these questions
  WHILE performing the experiment, not after reading a textbook.

  ── IN-LAB SCENARIO QUESTION TYPES (mandatory — use for ≥50% of questions) ──────────────────
  These put the student in the lab and require practical thinking:

  a) DOING-STEP scenarios — student is mid-experiment:
       "You are about to [specific step]. What must you do first?"
       "While [performing step X], you notice [observation]. What does this indicate?"
       "You have just completed [step]. What is the NEXT action you should take?"
       "During the experiment, [something unexpected happens]. What is the most likely cause?"

  b) DECISION-MAKING scenarios — student must choose the correct action:
       "You are setting up the apparatus. Which arrangement is correct?"
       "You need to measure [quantity]. Which instrument from the apparatus list should you use?"
       "The reading on [instrument] is [value]. What should you record?"
       "You complete three trials and get readings [X, Y, Z]. How do you calculate the final result?"

  c) TROUBLESHOOTING scenarios — something goes wrong during the experiment:
       "A student performs this experiment and finds [unexpected result]. What is the most likely error?"
       "The [instrument] shows zero error before starting. What should the student do?"
       "After performing the experiment, the conclusion does not match expected results. Which step most likely introduced the error?"

  d) SAFETY-IN-ACTION scenarios — practical safety during the experiment:
       "Before starting this experiment, which precaution is MOST important?"
       "During the experiment, the [apparatus] slips. What should the student do IMMEDIATELY?"
       (Use mcq_multiple for these — multiple precautions often apply together.)

  e) OBSERVATION-IN-PROGRESS — what the student sees as they perform:
       "As [variable] increases, what change do you observe in [measurement]?"
       "You are recording readings in a table. When [condition X] is true, what value do you expect?"
       "A student plots a graph of [X vs Y] from the experimental data. What shape should the graph be?"

  ── KNOWLEDGE/THEORY QUESTIONS (remaining ≤50%) ────────────────────────────────────────────
  These test understanding of the experimental science — not pure rote definition recall:
      - Aim / Purpose       : WHY is this experiment performed? What concept does it verify?
      - Apparatus           : What is the ROLE of each specific piece of equipment?
      - Theory / Concept    : Test formulas, laws, and principles AS USED in this experiment.
      - Procedure Steps     : Use rearrange — write each step's actual content as option_text.
      - Data Interpretation : What does the slope / graph shape / calculated value represent?
      - Conclusion          : What conclusion can be drawn from [specific result]?
      - Extension           : Apply the same principle to a novel real-world situation.

  ── RULES FOR ALL QUESTIONS ─────────────────────────────────────────────────────────────────
  • Rearrange questions MUST write each step's actual content as option_text —
    NEVER use labels like "Step 1", "Step 2", "Step A", or any numbered reference.
  • Safety and error questions MUST use mcq_multiple — multiple options can be correct.
  • Each question must test a DIFFERENT aspect of the experiment — no two questions
    should overlap in what they test.
  • Allowed phrases: "in this experiment", "using the apparatus", "during the experiment",
    "you are performing", "a student is conducting", "while setting up".
  • STRICTLY FORBIDDEN: "the text says", "the manual states", "as mentioned above",
    "refer to page X", "as shown in Table X.X", "according to the manual",
    "as described in the passage".
"""

_LAB_MANUAL_SELF_VERIFICATION = """
Self-verification for lab manual questions (do this before submitting):
  For each question, verify:
  ✓ At least half the questions use in-lab scenario framing ("you are performing", "during the experiment", "a student notices")
  ✓ Question requires the student to THINK or ACT — not just recall a definition
  ✓ Correct answer is clearly supported by the experiment content provided
  ✓ hint guides the student's practical thinking without revealing the answer
  ✓ explanation justifies the correct answer and why each distractor is wrong
  ✓ rearrange questions: all options have is_correct=true and a unique correct_order with actual step content (no "Step 1" labels)
  ✓ No two questions test the exact same step, observation, or fact
  ✓ No reference to page numbers, text sections, or "the manual says"
  ✓ Safety and error questions use mcq_multiple
  ✓ IMAGE CHECK: exactly 2 or 3 questions have image_prompt set — no more, no fewer. The chosen questions are apparatus/setup, observation/graph, or in-lab scenario with a visible setup. All other questions have image_prompt null or omitted.
  If any check fails — fix the question before submitting.
"""


def build_lab_manual_system_prompt(
    grade_level: int, subject: str = "", chapter: str = "", board: str = "CBSE"
) -> str:
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
        parts.append(f"Chapter/Experiment: {chapter}")
    context_line = " | ".join(parts)

    return f"""You are an expert science lab assessment designer. Your specialty is writing questions that make students THINK like they are physically inside the lab — making decisions, recording observations, troubleshooting problems, and choosing the next action — not just recalling what they read.

Your task is to generate MCQs for a science experiment assessment. At least half the questions must put the student in a real lab scenario (mid-experiment decision, troubleshooting, observation in progress, safety action). The remaining questions test the underlying scientific concepts and procedure knowledge that make sense of what happens in the lab.

Curriculum context: {context_line}
Grade calibration: {grade_note}

{_MOBILE_FORMAT_RULES}

{_LAB_MANUAL_RULES}

{_BLOOM_MAPPING}

{_DIFFICULTY_DISTRIBUTION_RULES}

{_QUESTION_TYPE_RULES}

{_ANSWER_POSITION_RULES}

{_HINT_RULES}

{_EXPLANATION_RULES}

{_LAB_MANUAL_IMAGE_RULES}

{_LAB_MANUAL_SELF_VERIFICATION}

Output format: return your response as structured JSON matching the provided schema. No markdown, no code fences, no plain text."""


def build_lab_manual_user_prompt(
    chapter: str,
    num_questions: int,
    context_text: str,
    existing_question_stems: list[str] | None = None,
) -> str:
    dedup_section = ""
    if existing_question_stems:
        stems_list = "\n".join(f"  - {s}" for s in existing_question_stems)
        dedup_section = f"\nAlready-asked questions (do NOT repeat these):\n{stems_list}\n"

    return f"""Experiment: {chapter}
Assessment Type: Lab Manual / Science Experiment
Number of questions to generate: {num_questions}
{dedup_section}
Experiment content (use ONLY the information below to create questions):
---
{context_text}
---

Generate exactly {num_questions} question(s) for this lab experiment. Follow this mandatory split:

IN-LAB SCENARIO questions (≥50% of total — these MUST be present):
  Write questions where the student is physically performing the experiment right now.
  Use stems like:
    • "You are performing this experiment and [situation]. What should you do?"
    • "While [specific step], you notice [observation]. What does this indicate?"
    • "You have completed [step]. What is the next correct action?"
    • "A student is conducting this experiment and [problem occurs]. What is the most likely cause?"
    • "Before starting, you must [safety action]. What is the reason for this?"
    • "You record the reading as [value]. Is this correct? Why / why not?"
  These questions should require the student to DECIDE, OBSERVE, or TROUBLESHOOT — not just recall.

KNOWLEDGE questions (remaining ≤50%):
  Test: aim/purpose (why this experiment), apparatus roles, underlying theory and formula,
  procedure step ordering (use rearrange), data interpretation, conclusion, and application.

Question type assignment:
  • rearrange for procedure step ordering — write each step's actual content, never "Step 1"
  • mcq_multiple for safety precautions and error analysis (multiple correct options)
  • mcq_single for all other questions

Difficulty: vary levels (1–5) to match cognitive demand — in-lab scenario questions typically fall at levels 3–5.

Images (MANDATORY — not optional for lab manuals):
  You MUST set image_prompt on EXACTLY 2 or 3 questions — no more, no less.
  Choose the 2–3 questions where a diagram adds the most value:
    • Apparatus/setup question → diagram of the apparatus arrangement with one part unlabelled or marked '?'
    • Observation/graph question → a graph with the data from this experiment plotted; mark the value being asked about with '?'
    • In-lab scenario with a visible setup → show the experiment at the step described in the question
  All other questions must have image_prompt set to null or omitted.
  The image must show the PROBLEM SETUP only — never the answer. Label all parts except the one being asked about.

Return all questions as a JSON array."""


# ── Lab Practical / Sequential Scenario prompts ───────────────────────────────

_LAB_PRACTICAL_RULES = """
Lab Practical assessment rules — CHAINED sequential scenario questions:

  CORE RULE — TRUE CHAIN: Questions within a group must be a CHAIN, not isolated scenarios.
  This means:
    • Q1 establishes an action or measurement
    • Q2's scenario states Q1's result as a FACT, then asks the next step
    • Q3's scenario states Q1 + Q2's results as FACTS, then asks the next step
    • Q4's scenario carries forward all prior results and reaches a decision or conclusion

  The student should feel they are progressing through ONE continuous experiment,
  with each question handing them the result of the previous step.

  ── CHAIN EXAMPLE (Hooke's Law) ────────────────────────────────────────────────
  Q1: "Scenario: You are about to perform the Hooke's Law experiment. The spring
       is hanging from the retort stand with no weights attached.
       What is the FIRST measurement you must record before adding any weights?"
       → Correct answer: natural / original length of the spring

  Q2: "Scenario: You recorded the natural length of the spring as 8.0 cm.
       You now place a 100 g slotted weight on the hanger and the spring stretches.
       The metre rule now reads 10.0 cm. What is the extension of the spring?"
       → Notice: Q2 states "You recorded the natural length as 8.0 cm" — Q1's result

  Q3: "Scenario: You recorded that a 100 g load produces a 2.0 cm extension.
       You add another 100 g weight (total load = 200 g).
       According to Hooke's Law, what extension should you now expect?"
       → Notice: Q3 states "100 g produces 2.0 cm" — Q2's result

  Q4: "Scenario: You have completed all trials. At 500 g load, you expected
       10.0 cm extension but observed only 8.5 cm.
       What does this tell you about the spring at this load?"
       → Notice: Q4 carries forward the established data and asks for the conclusion
  ── END EXAMPLE ────────────────────────────────────────────────────────────────

  HOW TO EMBED THE SCENARIO:
    Every question_text MUST start with "Scenario:" followed by 2–3 sentences:
      • State the accumulated facts/results from all previous questions in this group
      • Describe what is happening RIGHT NOW at this step
      Then on a new line, ask the specific question for this step.

    Format:
      "Scenario: [accumulated state from previous steps + current moment description]

      [The specific question for this step]"

  CHAIN STRUCTURE FOR ~10 QUESTIONS — generate 2–3 groups:

    Group 1 — Setup & First Measurement (3–4 questions chained)
      Q1: What to check / measure first (zero error, natural length, initial reading)
      Q2: Uses Q1's result — first action taken, first reading recorded
      Q3: Uses Q1+Q2 — applies the first reading to do something next
      Q4: Uses Q1+Q2+Q3 — a safety check, unit check, or pre-trial verification

    Group 2 — Performing Trials & Observing (3–4 questions chained)
      Q1: First trial — what to do, what to expect
      Q2: Uses trial-1 result — second trial, what changes, what to record
      Q3: Uses trial-1+2 results — pattern observed, expected next value
      Q4: Uses all trial results — anomaly or verification step

    Group 3 — Analysis & Conclusion (if questions remain, 2–3 questions chained)
      Q1: Plot the data — what does the graph look like?
      Q2: Uses the graph — what does the slope / intercept represent?
      Q3: Uses all results — draw the conclusion or identify the error source

  QUESTION TYPES:
    • mcq_single  : for most chain questions (one correct next action / reading / conclusion)
    • mcq_multiple: for safety precautions (typically Q4 of Group 1) and error analysis
    • Do NOT use rearrange — the chain IS the sequence

  IMAGES: set image_prompt on exactly 1–2 questions across the entire set:
    • Best: Group 1 Q1 — show the apparatus setup (label all parts except the one being asked about)
    • Second: Group 3 — show the graph plotted from the experimental data
    • All other questions: image_prompt must be null or omitted

  FORBIDDEN: "the text says", "the manual states", "refer to page X",
    "as shown in Table X.X", "according to the manual", "as described in the passage"
  ALLOWED: "you recorded", "you observed", "you measured", "you found that",
    "you have just", "at this stage", "continuing the experiment"
"""

_LAB_PRACTICAL_SELF_VERIFICATION = """
Self-verification for Lab Practical questions (do this before submitting):
  ✓ Questions within each group form a TRUE CHAIN — Q2's scenario states Q1's result,
    Q3's scenario states Q1+Q2 results, Q4 carries all prior results forward
  ✓ Every question_text starts with "Scenario:" and includes accumulated facts from prior steps
  ✓ No two questions in a group have identical or near-identical scenarios
  ✓ The student who reads Q3 can see exactly what happened in Q1 and Q2 from the scenario alone
  ✓ No rearrange questions — chain flow is embedded in the scenario progression
  ✓ Correct answer is clearly supported by the experiment content provided
  ✓ hint guides practical thinking without revealing the answer
  ✓ explanation justifies the correct answer and why each distractor is wrong
  ✓ No reference to page numbers, text sections, or "the manual says"
  ✓ Safety questions use mcq_multiple
  ✓ Exactly 1–2 questions have image_prompt set; all others have image_prompt null
  If any check fails — fix the question before submitting.
"""


def build_lab_practical_system_prompt(
    grade_level: int, subject: str = "", chapter: str = "", board: str = "CBSE"
) -> str:
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
        parts.append(f"Chapter/Experiment: {chapter}")
    context_line = " | ".join(parts)

    return f"""You are an expert science lab assessment designer specialising in practical experiment assessments. Your task is to write scenario-based sequential questions that walk a student through performing an experiment step by step.

Each question must begin with a short experimental scenario (2–3 sentences) describing the student at a specific moment in the lab. Questions within a group flow in the order the experiment actually happens — setup → performing → observing → analysing.

Curriculum context: {context_line}
Grade calibration: {grade_note}

{_MOBILE_FORMAT_RULES}

{_LAB_PRACTICAL_RULES}

{_BLOOM_MAPPING}

{_QUESTION_TYPE_RULES}

{_ANSWER_POSITION_RULES}

{_HINT_RULES}

{_EXPLANATION_RULES}

{_LAB_PRACTICAL_SELF_VERIFICATION}

Output format: return your response as a flat JSON array of question objects. No markdown, no code fences, no plain text."""


def build_lab_practical_user_prompt(
    chapter: str,
    num_questions: int,
    context_text: str,
    existing_question_stems: list[str] | None = None,
) -> str:
    dedup_section = ""
    if existing_question_stems:
        stems_list = "\n".join(f"  - {s}" for s in existing_question_stems)
        dedup_section = f"\nAlready-asked questions (do NOT repeat these):\n{stems_list}\n"

    if num_questions <= 4:
        group_plan = "Generate 1 scenario group with all questions."
    elif num_questions <= 7:
        group_plan = "Generate 2 scenario groups of 3–4 questions each."
    else:
        group_plan = "Generate 3 scenario groups covering: (1) Setup & Preparation, (2) Performing & Observing, (3) Analysis & Conclusion. Distribute questions evenly across the groups."

    return f"""Experiment: {chapter}
Assessment Type: Lab Practical — Chained Sequential Questions
Number of questions to generate: {num_questions}
{dedup_section}
Experiment content (use ONLY the information below to write scenarios and questions):
---
{context_text}
---

{group_plan}

CHAIN RULE — the most important instruction:
  Within each group, each question's scenario MUST state the result/reading/observation
  established by ALL previous questions in that group. Think of it as a running experiment log:
    Q1 scenario: the starting state
    Q2 scenario: "You recorded [Q1 result]. Now you [next action]..."
    Q3 scenario: "You recorded [Q1 result]. You found [Q2 result]. Now..."
    Q4 scenario: "You have recorded [Q1+Q2+Q3 results]. You now observe..."

  Use REAL values from the experiment (actual measurements, loads, readings from the PDF).
  The student reading Q3 must be able to see exactly what happened in Q1 and Q2
  from the scenario text alone — with no memory of the previous questions needed.

question_text format (strictly required):
  "Scenario: [accumulated experiment state + current moment]

  [The MCQ question for this step]"

Question types: mcq_single for most; mcq_multiple for safety/error analysis.
Do NOT use rearrange.
Images: exactly 1–2 questions across the full set (apparatus setup or graph). All others: null.
Difficulty: levels 2–4.

Return all {num_questions} questions as a flat JSON array."""


# ── Introduction to Experiment / Theory-Formula prompts ──────────────────────

_LAB_INTRO_RULES = """
Introduction to Experiment assessment rules — aim, formulas, and general theory ONLY:

  ══════════════════════════════════════════════════════════════════════
  HARD BOUNDARY — READ THIS FIRST:
  This topic covers ONLY the pre-lab knowledge: introduction, formulas,
  and scientific theory. It does NOT cover anything that happens during
  the experiment (procedure, steps, observations, data, safety, errors).
  If a question is about WHAT TO DO in the lab → reject it.
  If a question is about WHAT YOU OBSERVED or RECORDED → reject it.
  If a question asks to ARRANGE PROCEDURE STEPS → reject it.
  ══════════════════════════════════════════════════════════════════════

  SCOPE — generate questions from ONLY these three areas:

  1. AIM / PURPOSE / INTRODUCTION (~20–30% of questions)
     What this experiment is and WHY it is performed:
       • Which physical law or principle does this experiment verify?
       • What is the stated aim of this experiment?
       • What concept or relationship does the experiment demonstrate?
     Stems: "What is the aim of...", "Which law does this experiment verify?",
            "Why is this experiment performed?", "What does this experiment demonstrate?"

  2. FORMULAS AND MATHEMATICAL RELATIONSHIPS (~35–45% of questions)
     Test the key equations of the experiment:
       • What does each symbol in the formula represent?
       • What are the SI units of each quantity?
       • Rearrange the formula to find a given variable
       • Calculate a value given numerical data (use real values from the experiment content)
       • Which of these is the correct formula for this experiment?
       • If [variable] doubles / halves, what happens to [other quantity]?
     Stems: "In the formula F = kx, what does k represent?",
            "What are the SI units of the spring constant?",
            "Calculate the extension when a 200 g mass is hung...",
            "If the load is tripled and the spring obeys Hooke's Law, the extension..."

  3. GENERAL THEORY / UNDERLYING CONCEPTS (~30–40% of questions)
     The scientific principle behind the experiment:
       • State or identify the law being verified
       • What does the law state? (pick the correct word statement)
       • What is the physical meaning of the constant / slope / proportionality factor?
       • Within what conditions or limits does the law hold?
       • What happens when the law breaks down?
       • What TYPE of relationship does the law describe (linear, inverse, etc.)?
     Stems: "Hooke's Law states that...", "The spring constant is a measure of...",
            "The law is valid only as long as...", "The slope of the F vs x graph represents...",
            "Beyond the elastic limit, the spring..."

  STRICTLY EXCLUDED — these question types are FORBIDDEN in this topic:
    ✗ Any question about experimental procedure steps
        BAD: "What is the first step in the procedure?"
        BAD: "Arrange the procedure steps in the correct order."
        BAD: "What should you do after adding the mass?"
    ✗ Any question about recording observations or reading data
        BAD: "What is the primary goal when analyzing the data?"
        BAD: "What value did the student record?"
    ✗ Any question about safety precautions
    ✗ Any question about error analysis or troubleshooting
    ✗ Any question using in-lab scenario framing ("you are performing...", "a student is in the lab...")
    ✗ Generic scientific method questions not specific to this experiment's theory
        BAD: "Why is it important to change only one variable at a time?"
    These belong to the Lab Manual and Lab Practical topics.

  QUESTION TYPES:
    • mcq_single  : for most questions (factual, formula, and concept)
    • mcq_multiple: when multiple statements of a law or multiple correct aspects genuinely apply
                    (e.g., "Which of the following are correct statements of Hooke's Law?")
    • rearrange   : ONLY for ordering steps in a formula derivation
                    — write the actual content of each step, NEVER "Step 1", "Step 2"
                    — NEVER use rearrange for procedure steps

  IMAGES — set image_prompt on at most 1–2 questions:
    • A free-body / force diagram illustrating the formula derivation
    • A graph shape showing the mathematical relationship (e.g., F vs x with slope k marked)
    • Do NOT use apparatus setup diagrams here — those belong to Lab Manual
    • All other questions: image_prompt null or omitted
"""

_LAB_INTRO_SELF_VERIFICATION = """
Self-verification for Introduction to Experiment questions (do this before submitting):
  SCOPE CHECK — reject and rewrite any question that fails these:
  ✗ Does the question ask about a procedure step or what to do in the lab? → REWRITE as theory/formula
  ✗ Does the question ask about recording observations, data analysis, or graph results? → REWRITE
  ✗ Does the question use in-lab scenario framing ("you are performing...", "a student notices...")? → REWRITE
  ✗ Is the question about a generic scientific method rule (e.g., "change one variable")? → REWRITE
  ✗ Does the question ask to arrange/order procedure steps? → DELETE (rearrange is for formula derivation only)

  QUALITY CHECK — verify each accepted question:
  ✓ Tests ONLY: aim/purpose, formula symbol/unit/calculation, or scientific theory/law
  ✓ Formula questions use correct symbols and SI units from the experiment content
  ✓ Theory questions test conceptual understanding — not just rote definition recall
  ✓ Numerical questions use real values extracted from the experiment content
  ✓ question_text, hint, and explanation contain NO reference to "the text", "the manual",
    "the passage", "according to the text", "the text explicitly states", "as mentioned above"
  ✓ hint guides the student's conceptual thinking without revealing the answer
  ✓ explanation states the correct principle, formula, or definition clearly and concisely (≤300 chars)
  ✓ At most 1–2 questions have image_prompt set; all others have image_prompt null
  If any check fails — fix the question before submitting.
"""


def build_lab_intro_system_prompt(
    grade_level: int, subject: str = "", chapter: str = "", board: str = "CBSE"
) -> str:
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
        parts.append(f"Chapter/Experiment: {chapter}")
    context_line = " | ".join(parts)

    return f"""You are an expert science assessment designer specialising in the theoretical and mathematical foundations of laboratory experiments.

Your task is to generate MCQs that test a student's understanding of the introduction, purpose, formulas, and general theory of a science experiment — the conceptual groundwork a student must have before stepping into the lab.

Curriculum context: {context_line}
Grade calibration: {grade_note}

{_MOBILE_FORMAT_RULES}

{_SOURCE_INDEPENDENCE_RULES}

{_LAB_INTRO_RULES}

{_BLOOM_MAPPING}

{_DIFFICULTY_DISTRIBUTION_RULES}

{_QUESTION_TYPE_RULES}

{_ANSWER_POSITION_RULES}

{_HINT_RULES}

{_EXPLANATION_RULES}

{_LAB_INTRO_SELF_VERIFICATION}

Output format: return your response as structured JSON matching the provided schema. No markdown, no code fences, no plain text."""


def build_lab_intro_user_prompt(
    chapter: str,
    num_questions: int,
    board: str = "CBSE",
    grade_level: int = 8,
    existing_question_stems: list[str] | None = None,
) -> str:
    dedup_section = ""
    if existing_question_stems:
        stems_list = "\n".join(f"  - {s}" for s in existing_question_stems)
        dedup_section = f"\nAlready-asked questions (do NOT repeat these):\n{stems_list}\n"

    return f"""Experiment: {chapter}
Assessment Type: Introduction to Experiment — Aim, Formula & Theory
Board: {board} | Grade: {grade_level}
Number of questions to generate: {num_questions}
{dedup_section}
Use your knowledge of the {board} Class {grade_level} science curriculum to generate questions
about the introduction, formulas, and general theory of this experiment: "{chapter}".

Generate exactly {num_questions} question(s) from ONLY these three areas:

AREA 1 — AIM / PURPOSE (~20–30% of questions):
  What is this experiment? Which law or principle does it verify? Why is it performed?
  Example stems: "What is the aim of this experiment?", "Which law does this experiment verify?",
  "What does this experiment demonstrate?", "Why is this experiment performed?"

AREA 2 — FORMULAS AND MATHEMATICAL RELATIONSHIPS (~35–45% of questions):
  Key equations of this experiment: symbol meanings, SI units, rearrangements, calculations.
  Example stems: "In the formula [formula], what does [symbol] represent?",
  "What are the SI units of [quantity]?", "If [variable] is doubled, what happens to [quantity]?",
  "Calculate [value] given [data]."

AREA 3 — GENERAL THEORY / UNDERLYING CONCEPTS (~30–40% of questions):
  The scientific principle governing this experiment: what the law states, physical meaning
  of constants, type of relationship, validity limits, what happens when the law breaks down.
  Example stems: "[Law name] states that...", "The [constant] represents...",
  "The law holds only when...", "The slope of the [graph] represents..."

DO NOT generate any question about:
  ✗ Procedure steps or experimental actions
  ✗ Observations, recorded data, or data tables
  ✗ Safety precautions
  ✗ In-lab scenarios
  ✗ Generic scientific method rules

Question types: mcq_single for most; mcq_multiple when multiple aspects are genuinely correct;
rearrange ONLY for formula derivation steps (never for procedure steps).
Difficulty: level 1 (recall aim/law) to level 4 (formula manipulation, novel application).
Images: at most 1–2 — force/free-body diagrams or graph shape diagrams only.

Return all questions as a JSON array."""


# ── Experiment Setup prompts ──────────────────────────────────────────────────

_LAB_SETUP_RULES = """
Experiment Setup assessment rules — apparatus and procedure steps ONLY:

  SCOPE — generate questions from ONLY these two areas:

  1. APPARATUS / EQUIPMENT (~40–50% of questions)
     Questions about the equipment used to set up this experiment:
       • Identify each piece of apparatus by name
       • What is the ROLE or PURPOSE of each specific piece of equipment?
       • Which instrument is used to measure a specific quantity?
       • What is the correct arrangement or connection of the apparatus?
       • Which piece of equipment is NOT needed for this experiment?
     Stems: "Which instrument is used to measure...",
            "What is the role of [apparatus] in this experiment?",
            "Which of the following is NOT part of the apparatus for this experiment?",
            "How should [apparatus] be positioned / connected?"

  2. SETUP PROCEDURE / STEPS (~50–60% of questions)
     Questions about HOW to set up and take a reading in this experiment:
       • Rearrange the setup or measurement steps in the correct order
       • What is done FIRST before starting the experiment?
       • What must be checked or calibrated before taking measurements?
       • What is the correct next step at a specific point in the setup?
     Stems: "Arrange the following setup steps in the correct order.",
            "What is the first action before adding any [variable]?",
            "Before starting the experiment, which check must be performed?",
            "What is the correct order of steps to take one measurement?"

  QUESTION TYPES — IMPORTANT:
    • rearrange : REQUIRED — use for most procedure/step questions.
                  Write each step's ACTUAL CONTENT as option_text.
                  NEVER use "Step 1", "Step 2", "Step A", or any numbered labels.
                  All options must have is_correct=true with a unique correct_order.
    • mcq_single : for apparatus identification, role, and single-step questions
    • mcq_multiple: for "which of these are required apparatus?" (multiple correct items)
    • Aim for at least 40% rearrange questions across the set

  IMAGES — set image_prompt on exactly 1–2 questions:
    • Best choice: an apparatus/setup diagram — show the full arrangement with one
      component unlabelled (marked '?') for the question being asked
    • Second choice: a partial setup diagram showing the arrangement being asked about
    • All other questions: image_prompt null or omitted

  STRICTLY EXCLUDED — do NOT generate any question on:
    ✗ Theory or scientific laws (formulas, equations, proportionality)
    ✗ Calculations or formula manipulation
    ✗ Observations, readings, or data recording during the experiment
    ✗ Data analysis or graph interpretation
    ✗ Conclusions or error analysis
    ✗ In-lab scenario framing ("you are performing...", "you notice...")
    These belong to Introduction to Experiment, Lab Manual, and Lab Practical topics.
"""

_LAB_SETUP_SELF_VERIFICATION = """
Self-verification for Experiment Setup questions (do this before submitting):
  ✓ Every question is about apparatus identification/role OR setup/procedure steps
  ✓ NO question asks about theory, formulas, calculations, observations, or data
  ✓ rearrange questions: ALL options have is_correct=true with unique correct_order values
  ✓ rearrange option_text contains actual step content — NEVER "Step 1", "Step 2" labels
  ✓ At least 40% of questions are rearrange type
  ✓ Exactly 1–2 questions have image_prompt set (apparatus diagram); all others null
  ✓ No reference to "the text says", "the manual states", "according to the passage"
  If any check fails — fix the question before submitting.
"""


def build_lab_setup_system_prompt(
    grade_level: int, subject: str = "", chapter: str = "", board: str = "CBSE"
) -> str:
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
        parts.append(f"Chapter/Experiment: {chapter}")
    context_line = " | ".join(parts)

    return f"""You are an expert science assessment designer specialising in laboratory apparatus and experimental procedure.

Your task is to generate MCQs that test a student's knowledge of HOW to set up a science experiment — the equipment required, the role of each piece of apparatus, and the correct sequence of setup and measurement steps.

Curriculum context: {context_line}
Grade calibration: {grade_note}

{_MOBILE_FORMAT_RULES}

{_SOURCE_INDEPENDENCE_RULES}

{_LAB_SETUP_RULES}

{_BLOOM_MAPPING}

{_DIFFICULTY_DISTRIBUTION_RULES}

{_QUESTION_TYPE_RULES}

{_ANSWER_POSITION_RULES}

{_HINT_RULES}

{_EXPLANATION_RULES}

{_LAB_SETUP_SELF_VERIFICATION}

Output format: return your response as structured JSON matching the provided schema. No markdown, no code fences, no plain text."""


def build_lab_setup_user_prompt(
    chapter: str,
    num_questions: int,
    context_text: str,
    existing_question_stems: list[str] | None = None,
) -> str:
    dedup_section = ""
    if existing_question_stems:
        stems_list = "\n".join(f"  - {s}" for s in existing_question_stems)
        dedup_section = f"\nAlready-asked questions (do NOT repeat these):\n{stems_list}\n"

    return f"""Experiment: {chapter}
Assessment Type: Experiment Setup — Apparatus & Procedure Steps
Number of questions to generate: {num_questions}
{dedup_section}
Experiment content (use ONLY the information below to create questions):
---
{context_text}
---

Generate exactly {num_questions} question(s) covering ONLY apparatus knowledge and setup procedure steps.
Do NOT generate any question about theory, formulas, calculations, observations, or data.

AREA 1 — APPARATUS (~40–50% of questions):
  Equipment names, roles, and arrangement for this experiment.
  Example stems:
    "Which instrument is used to measure [quantity] in this experiment?"
    "What is the role of [apparatus] in the experimental setup?"
    "Which of the following is NOT required for this experiment?"
    "How should [apparatus] be positioned in the setup?"

AREA 2 — SETUP PROCEDURE STEPS (~50–60% of questions):
  The correct sequence of steps to set up the apparatus and take a measurement.
  Use rearrange type for most of these — write each step's actual action as option_text.
  Example stems:
    "Arrange the following steps to set up the apparatus in the correct order."
    "Arrange the following actions to take one complete measurement in the correct order."
    "What is the FIRST step before beginning the experiment?"
    "Before recording any readings, what must be done?"

Question type assignment:
  • rearrange for procedure step ordering — at least 40% of total questions
    → Each option_text must be the actual step content
       e.g. "Hang the spring from the retort stand", "Attach the slotted mass hanger to the spring"
    → NEVER write "Step 1", "Step 2", or any numbered label as option_text
  • mcq_single for apparatus role, identification, and single-step questions
  • mcq_multiple when multiple apparatus items are all required or correct

Difficulty: level 1 (name the apparatus) to level 3 (correct step sequence, role of specific equipment).
Images: exactly 1–2 questions — apparatus setup diagram with one component unlabelled ('?').

Return all questions as a JSON array."""


# ── Setup Practical / Chained Setup Questions ─────────────────────────────────

_SETUP_PRACTICAL_RULES = """
Setup Practical assessment rules — CHAINED sequential setup questions:

  CORE RULE — TRUE CHAIN (setup edition):
  Questions within a group walk the student through assembling and preparing the
  experiment step by step. Each question's scenario carries forward EXACTLY what
  has been set up so far, so the student always knows the current state.

    • Q1 — starting state: nothing is set up yet; ask what to do first
    • Q2 — scenario states what Q1 established; ask what to add or do next
    • Q3 — scenario states Q1 + Q2 state; ask the next setup action
    • Q4 — scenario states the full accumulated setup; ask the final preparation step

  ── CHAIN EXAMPLE (Hooke's Law setup) ─────────────────────────────────────────
  Q1: "Scenario: You are about to set up the Hooke's Law experiment. You have all
       the apparatus in front of you: a retort stand, a bent aluminium rod, a spring,
       a slotted mass hanger with pointer, a metal ruler, and slotted masses.
       What is the FIRST thing you should assemble?"
       → Answer: Attach the bent aluminium rod to the top of the retort stand

  Q2: "Scenario: You have attached the bent aluminium rod to the top of the retort
       stand. You now need to add the spring to the setup.
       Where should the spring be attached?"
       → Answer: Hung from the hook at the end of the bent aluminium rod
       → Notice: Q2 states 'You have attached the bent aluminium rod' — Q1's result

  Q3: "Scenario: You have attached the bent aluminium rod to the retort stand and
       hung the spring from it. You now attach the slotted mass hanger with pointer
       to the bottom of the spring.
       What must you position NEXT to be able to take readings?"
       → Answer: The metal ruler alongside the spring
       → Notice: Q3 carries forward both Q1 and Q2 results

  Q4: "Scenario: You have the retort stand with aluminium rod, spring, and slotted
       mass hanger all assembled. The metal ruler is positioned alongside the spring.
       Before adding any masses, what is the one reading you must record first?"
       → Answer: The initial (zero) reading of the pointer on the ruler
       → Notice: Q4 describes the complete setup built up from Q1-Q3
  ── END EXAMPLE ────────────────────────────────────────────────────────────────

  SCENARIO FORMAT — every question_text MUST start with "Scenario:":
    "Scenario: [describe exactly what has been assembled/done so far]

    [The setup question for this step]"

  CHAIN STRUCTURE FOR ~10 QUESTIONS — generate 2–3 groups:

    Group 1 — Assembling the Apparatus (3–4 questions)
      Q1: What to do first (base, stand, first component)
      Q2: Uses Q1 → what to attach or connect next
      Q3: Uses Q1+Q2 → what to add next (measuring instrument, etc.)
      Q4: Uses Q1+Q2+Q3 → final check or zero reading before starting

    Group 2 — Preparing to Measure (3–4 questions)
      Q1: Apparatus is assembled → what initial check or calibration to perform
      Q2: Uses Q1 → what to verify about the measuring instrument alignment
      Q3: Uses Q1+Q2 → what to confirm before the first mass is added
      Q4: Uses Q1+Q2+Q3 → what the student is now ready to do

    Group 3 — First Measurement Setup (if questions remain, 2–3 questions)
      Q1: Setup is complete → what is the correct way to add the first change
      Q2: Uses Q1 → what to do immediately after adding the first change
      Q3: Uses Q1+Q2 → what to verify before recording the reading

  QUESTION TYPES:
    • mcq_single: for most chain questions (one correct next action)
    • mcq_multiple: for "which of these must be checked?" setup verifications
    • Do NOT use rearrange — the chain IS the sequence

  IMAGES: set image_prompt on exactly 1–2 questions:
    • Best: Group 1 Q1 — show all apparatus laid out, one unlabelled ('?')
    • Second: Group 1 Q3 or Q4 — show partially assembled setup
    • All others: image_prompt null or omitted

  STRICTLY EXCLUDED:
    ✗ Theory, formulas, calculations (e.g. "What does k represent?")
    ✗ Observations or data recording (e.g. "What value did you read?")
    ✗ Data analysis or conclusions
    ✗ Full in-lab experiment scenarios (adding masses, watching spring stretch)
    These belong to Introduction to Experiment, Lab Manual, and Lab Practical topics.

  FORBIDDEN: "the text says", "the manual states", "according to the passage"
  ALLOWED: "you have assembled", "you have attached", "you have positioned",
           "you have verified", "the setup now has", "continuing the setup"
"""

_SETUP_PRACTICAL_SELF_VERIFICATION = """
Self-verification for Setup Practical questions (do this before submitting):
  ✓ Questions within each group form a TRUE CHAIN — Q2 states what Q1 established,
    Q3 states Q1+Q2, Q4 carries the full accumulated setup state
  ✓ Every question_text starts with "Scenario:" describing current setup state
  ✓ No two questions in a group describe the same setup state
  ✓ All questions are about SETUP ONLY — no theory, no formula, no data
  ✓ No rearrange questions — the chain flow handles the sequence
  ✓ hint guides the student toward the correct next setup action
  ✓ explanation justifies why this is the correct next step and why others are wrong
  ✓ Exactly 1–2 questions have image_prompt; all others null
  ✓ No reference to "the text says", "the manual states", "refer to page X"
  If any check fails — fix the question before submitting.
"""


def build_setup_practical_system_prompt(
    grade_level: int, subject: str = "", chapter: str = "", board: str = "CBSE"
) -> str:
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
        parts.append(f"Chapter/Experiment: {chapter}")
    context_line = " | ".join(parts)

    return f"""You are an expert science assessment designer specialising in laboratory setup and apparatus assembly.

Your task is to generate chained sequential MCQs that walk a student step by step through the process of SETTING UP a science experiment — from unpacking the apparatus to being ready to take the first measurement. Each question must begin with a scenario describing exactly what has been assembled so far, and ask what to do next.

Curriculum context: {context_line}
Grade calibration: {grade_note}

{_MOBILE_FORMAT_RULES}

{_SOURCE_INDEPENDENCE_RULES}

{_SETUP_PRACTICAL_RULES}

{_BLOOM_MAPPING}

{_QUESTION_TYPE_RULES}

{_ANSWER_POSITION_RULES}

{_HINT_RULES}

{_EXPLANATION_RULES}

{_SETUP_PRACTICAL_SELF_VERIFICATION}

Output format: return your response as a flat JSON array of question objects. No markdown, no code fences, no plain text."""


def build_setup_practical_user_prompt(
    chapter: str,
    num_questions: int,
    context_text: str,
    existing_question_stems: list[str] | None = None,
) -> str:
    dedup_section = ""
    if existing_question_stems:
        stems_list = "\n".join(f"  - {s}" for s in existing_question_stems)
        dedup_section = f"\nAlready-asked questions (do NOT repeat these):\n{stems_list}\n"

    if num_questions <= 4:
        group_plan = "Generate 1 setup chain group with all questions."
    elif num_questions <= 7:
        group_plan = "Generate 2 setup chain groups of 3–4 questions each."
    else:
        group_plan = "Generate 3 setup chain groups: (1) Assembling the Apparatus, (2) Preparing to Measure, (3) First Measurement Setup. Distribute questions evenly."

    return f"""Experiment: {chapter}
Assessment Type: Setup Practical — Chained Sequential Setup Questions
Number of questions to generate: {num_questions}
{dedup_section}
Experiment content (use ONLY the information below to write scenarios and questions):
---
{context_text}
---

{group_plan}

CHAIN RULE — most important instruction:
  Within each group, each question's scenario MUST state exactly what has been
  assembled or done in ALL previous questions. Think of it as an assembly log:
    Q1 scenario: "You are about to set up... You have [list all apparatus]..."
    Q2 scenario: "You have [Q1 action]. You now need to [next phase]..."
    Q3 scenario: "You have [Q1 action] and [Q2 action]. What must you [next]?"
    Q4 scenario: "You have [Q1+Q2+Q3 actions complete]. The setup now has [state]..."

  Use the ACTUAL apparatus names from the experiment content.
  The student reading Q3 must know exactly what has been set up from Q1 and Q2
  just by reading Q3's scenario alone.

question_text format (strictly required):
  "Scenario: [exact current state of the setup — what has been assembled so far]

  [The setup question for this step]"

Question types: mcq_single for most; mcq_multiple for setup verification checks.
Do NOT use rearrange — the chain handles the sequence.
Images: exactly 1–2 questions (apparatus layout or partial assembly). All others: null.
Difficulty: levels 1–3 (setup knowledge and sequencing).

Return all {num_questions} questions as a flat JSON array."""
