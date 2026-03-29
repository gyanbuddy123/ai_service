"""
MCQ validation: schema checks, dedup, and hint quality verification.
"""
import hashlib
import re

_STOP_WORDS = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'shall', 'can', 'to', 'of', 'in', 'on', 'at',
    'by', 'for', 'with', 'as', 'it', 'its', 'this', 'that', 'and', 'or',
    'but', 'if', 'then', 'so', 'not', 'no', 'nor',
}

# Rejection reasons that can be repaired via modify_question
_FIXABLE_REASONS = {
    "Hint reveals the correct answer",
    "No correct answer marked",
    "difficulty_level must be 1–5",
}


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text.strip().lower())


def question_hash(question_text: str) -> str:
    return hashlib.sha256(normalize_text(question_text).encode()).hexdigest()


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z']+", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def hint_leaks_answer(hint: str, correct_option_texts: list[str]) -> bool:
    """
    Returns True only when the hint meaningfully reveals the correct answer.

    Rules:
    - Single-word overlap is NOT enough — requires 2+ overlapping content words,
      OR a single overlap where that word is the dominant/sole noun in the answer
      (i.e. the answer is 1–2 words long and the overlap is its core word).
    - Short generic words (len <= 3) are ignored even if not in stop words.
    - This avoids rejecting hints that merely share topic-domain vocabulary.
    """
    hint_tokens = _tokenize(hint)
    # Drop very short tokens (e.g. "law", "ion") — too common in CBSE content
    hint_tokens = {w for w in hint_tokens if len(w) > 3}

    for option_text in correct_option_texts:
        answer_tokens = _tokenize(option_text)
        answer_tokens = {w for w in answer_tokens if len(w) > 3}
        overlap = hint_tokens & answer_tokens

        if not overlap:
            continue

        # Short answer (1-2 meaningful words) — even one overlap is a leak
        if len(answer_tokens) <= 2 and overlap:
            return True

        # Longer answer — require 2+ overlapping words to flag as a leak
        if len(overlap) >= 2:
            return True

    return False


def is_fixable(rejection_reason: str) -> bool:
    """Return True if the rejection can be repaired via modify_question."""
    return rejection_reason in _FIXABLE_REASONS


def fix_instruction(rejection_reason: str) -> tuple[str, str]:
    """
    Return (modification_type, instruction) for a fixable rejection reason.
    """
    if rejection_reason == "Hint reveals the correct answer":
        return (
            "CUSTOM",
            "Rewrite only the hint field so it does not contain any word from the correct answer. "
            "Guide the student's thinking without naming or implying the correct option. "
            "Keep everything else identical.",
        )
    if rejection_reason == "No correct answer marked":
        return (
            "CUSTOM",
            "Exactly one option must have is_correct=true. "
            "Fix the is_correct flags without changing any option text.",
        )
    if rejection_reason == "difficulty_level must be 1–5":
        return (
            "CHANGE_DIFFICULTY",
            "Set difficulty_level to 3.",
        )
    # Fallback (should not be reached for non-fixable reasons)
    return ("CUSTOM", "Fix the issue with this question.")


def validate_single(q: dict, seen_hashes: set[str]) -> str | None:
    """
    Validate a single question against seen_hashes.
    Returns rejection reason string, or None if valid.
    Mutates seen_hashes on success — add the hash after calling this.
    """
    return _check_question(q, seen_hashes)

def _check_question(q: dict, seen_hashes: set[str]) -> str | None:
    # Required fields
    if not q.get('question_text'):
        return "Missing required field: question_text"

    question_type = q.get('question_type', 'mcq_single')
    options = q.get('options', [])

    if not isinstance(options, list) or len(options) < 2:
        return "options must be a list with at least 2 items"

    # Each option needs option_text and is_correct
    for opt in options:
        if not isinstance(opt, dict):
            return "Each option must be an object"
        if 'option_text' not in opt:
            return "Each option must have option_text"
        if 'is_correct' not in opt:
            return "Each option must have is_correct"

    if question_type == 'rearrange':
        # For rearrange: all options must be correct and have correct_order
        for opt in options:
            if not opt.get('is_correct'):
                return "All rearrange options must have is_correct=true"
            if 'correct_order' not in opt or not isinstance(opt.get('correct_order'), int):
                return "All rearrange options must have correct_order (integer)"
        n = len(options)
        if not (4 <= n <= 6):
            return "Rearrange questions must have 4–6 options"
        orders = sorted(opt['correct_order'] for opt in options)
        if orders != list(range(1, n + 1)):
            return "Rearrange correct_order values must be contiguous from 1 to N"
    else:
        # mcq_single / mcq_multiple: exactly 4 options, at least one correct
        if len(options) != 4:
            return "MCQ questions must have exactly 4 options"
        correct_options = [o for o in options if o.get('is_correct')]
        if not correct_options:
            return "No correct answer marked"
        if question_type == 'mcq_single' and len(correct_options) > 1:
            return "mcq_single must have exactly one correct answer"

    # Difficulty range
    try:
        diff = int(q.get('difficulty_level', 0))
    except (TypeError, ValueError):
        return "difficulty_level must be an integer"
    if not 1 <= diff <= 5:
        return "difficulty_level must be 1–5"

    # Dedup
    h = question_hash(q.get('question_text', ''))
    if h in seen_hashes:
        return "Duplicate question (hash match)"

    # Hint quality (skip for rearrange — all options are correct)
    if question_type != 'rearrange':
        hint = q.get('hint', '')
        if hint:
            correct_options = [o for o in options if o.get('is_correct')]
            correct_texts = [o.get('option_text', '') for o in correct_options]
            if hint_leaks_answer(hint, correct_texts):
                return "Hint reveals the correct answer"

    return None

def validate_questions(
    raw_questions: list[dict],
    seen_hashes: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    seen_hashes = seen_hashes or set()
    valid: list[dict] = []
    rejected: list[dict] = []

    for q in raw_questions:
        reason = _check_question(q, seen_hashes)
        if reason:
            q['rejection_reason'] = reason
            rejected.append(q)
        else:
            seen_hashes.add(question_hash(q.get('question_text', '')))
            valid.append(q)

    return valid, rejected
