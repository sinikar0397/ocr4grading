def merge_by_number(exam_questions: list[dict], answer_questions: list[dict]) -> list[dict]:
    """Combine exam-paper questions (question_text) with answer-key questions
    (answer/explanation) into one draft list, keyed by question number.

    Either side may be missing an entry for a given number (mismatched OCR,
    typo, etc.) -- those fields just come back as None for the user to fix
    in the preview/confirm UI.
    """
    by_number: dict[str, dict] = {}
    for eq in exam_questions:
        number = str(eq["number"])
        by_number[number] = {
            "number": number,
            "question_text": eq.get("question_text"),
            "answer": None,
            "explanation": None,
        }
    for aq in answer_questions:
        number = str(aq["number"])
        entry = by_number.setdefault(number, {"number": number, "question_text": None, "answer": None, "explanation": None})
        entry["answer"] = aq.get("answer")
        entry["explanation"] = aq.get("explanation")

    return [by_number[number] for number in sorted(by_number, key=lambda n: (len(n), n))]


def pair_questions(student_qs: list[dict], reference_qs: dict[str, str]) -> list[dict]:
    """Match OCR'd student answers to DB reference answers by question number.

    Questions with no reference answer in the DB are flagged as
    "missing_reference" instead of graded, so the caller can prompt the user
    to fill them in manually.
    """
    pairs = []
    for sq in student_qs:
        number = str(sq["number"])
        ref = reference_qs.get(number)
        base = {
            "number": number,
            "student_solution": sq.get("solution"),
        }
        if ref is None:
            pairs.append({**base, "status": "missing_reference"})
        else:
            pairs.append({
                **base,
                "status": "to_grade",
                "correct_answer": ref,
            })
    return pairs
