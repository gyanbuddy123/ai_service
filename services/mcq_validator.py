"""
MCQ validation: schema checks, dedup, and hint quality verification.
"""
import hashlib
import re

# Common English stop words to ignore during hint quality check
_STOP_WORDS = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'shall', 'can', 'to', 'of', 'in', 'on', 'at',
    'by', 'for', 'with', 'as', 'it', 'its', 'this', 'that', 'and', 'or',
    'but', 'if', 'then', 'so', 'not', 'no', 'nor',
}


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text.strip().lower())


def question_hash(question_text: str) -> str:
    return hashlib.sha256(normalize_text(question_text).encode()).hexdigest()


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z']+", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def hint_leaks_answer(hint: str, correct_option_texts: list[str]) -> bool:
    """Return True if hint contains any meaningful token from a correct answer."""
    hint_tokens = _tokenize(hint)
    for option_text in correct_option_texts:
        answer_tokens = _tokenize(option_text)
        if hint_tokens & answer_tokens:
            return True
    return False


def validate_questions(
    raw_questions: list[dict],
    seen_hashes: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Validate a list of raw question dicts.

    Returns:
        (valid_questions, rejected_questions)
        Each rejected dict has an extra 'rejection_reason' key.
    """
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


def _check_question(q: dict, seen_hashes: set[str]) -> str | None:
    """Return rejection reason string, or None if valid."""
    # Required fields
    for field in ('question_text', 'options', 'correct_answers', 'difficulty_level'):
        if not q.get(field):
            return f"Missing required field: {field}"

    options = q['options']
    correct_answers = q['correct_answers']

    # Options must be a non-empty list with key+text
    if not isinstance(options, list) or len(options) < 2:
        return "options must be a list with at least 2 items"

    option_keys = {o.get('key') for o in options if isinstance(o, dict)}
    for key in correct_answers:
        if key not in option_keys:
            return f"correct_answer key '{key}' not in options"

    # Difficulty range
    try:
        diff = int(q['difficulty_level'])
    except (TypeError, ValueError):
        return "difficulty_level must be an integer"
    if not 1 <= diff <= 5:
        return "difficulty_level must be 1–5"

    # Dedup
    h = question_hash(q.get('question_text', ''))
    if h in seen_hashes:
        return "Duplicate question (hash match)"

    # Hint quality
    hint = q.get('hint', '')
    if hint:
        correct_texts = [
            o.get('text', '') for o in options
            if isinstance(o, dict) and o.get('key') in correct_answers
        ]
        if hint_leaks_answer(hint, correct_texts):
            return "Hint reveals the correct answer"

    return None
