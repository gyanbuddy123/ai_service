"""
Post-generation answer position shuffler.
Ensures the correct answer is not always in the same position across questions.
Skips rearrange questions (order is semantically meaningful).
"""
from __future__ import annotations

import random


def _correct_position(options: list[dict]) -> int | None:
    """Return the index of the first correct option, or None."""
    for i, opt in enumerate(options):
        if opt.get("is_correct"):
            return i
    return None


def shuffle_answer_positions(questions: list[dict]) -> list[dict]:
    """
    Shuffle option order for mcq_single/mcq_multiple questions to avoid
    the correct answer always landing in the same position.

    Rule: if the correct answer appears in the same position for 3 or more
    consecutive questions, shuffle the middle question(s).

    Returns the (possibly modified) questions list in-place.
    """
    if len(questions) < 3:
        return questions

    # First pass: shuffle each MCQ question's options randomly so the AI's
    # natural ordering bias is broken, then verify distribution.
    for q in questions:
        if q.get("question_type", "mcq_single") == "rearrange":
            continue
        options = q.get("options", [])
        if len(options) < 2:
            continue
        random.shuffle(options)
        q["options"] = options

    # Second pass: fix runs of 3+ identical positions
    i = 0
    while i < len(questions) - 2:
        q0 = questions[i]
        q1 = questions[i + 1]
        q2 = questions[i + 2]

        # Skip rearrange
        if any(q.get("question_type") == "rearrange" for q in [q0, q1, q2]):
            i += 1
            continue

        # run-of-3 check only meaningful for mcq_single (one definitive correct position)
        if any(q.get("question_type") == "mcq_multiple" for q in [q0, q1, q2]):
            i += 1
            continue

        p0 = _correct_position(q0.get("options", []))
        p1 = _correct_position(q1.get("options", []))
        p2 = _correct_position(q2.get("options", []))

        if p0 is not None and p0 == p1 == p2:
            # Reshuffle the middle question until the position changes
            opts = q1.get("options", [])
            if len(opts) >= 2:
                for _ in range(10):  # max attempts
                    random.shuffle(opts)
                    if _correct_position(opts) != p0:
                        q1["options"] = opts
                        break
        i += 1

    return questions
