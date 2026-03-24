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


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text.strip().lower())


def question_hash(question_text: str) -> str:
    return hashlib.sha256(normalize_text(question_text).encode()).hexdigest()


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z']+", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def hint_leaks_answer(hint: str, correct_option_texts: list[str]) -> bool:
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
    # Required fields
    if not q.get('question_text'):
        return "Missing required field: question_text"

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

    # At least one correct answer
    correct_options = [o for o in options if o.get('is_correct')]
    if not correct_options:
        return "No correct answer marked"

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

    # Hint quality
    hint = q.get('hint', '')
    if hint:
        correct_texts = [o.get('option_text', '') for o in correct_options]
        if hint_leaks_answer(hint, correct_texts):
            return "Hint reveals the correct answer"

    return None
