def pair_questions(student_qs: list[dict], reference_qs: dict[str, dict]) -> list[dict]:
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
            "student_answer": sq.get("answer"),
            "student_solution": sq.get("solution"),
        }
        if ref is None or not ref.get("correct_answer"):
            pairs.append({**base, "status": "missing_reference"})
        else:
            pairs.append({
                **base,
                "status": "to_grade",
                "correct_answer": ref["correct_answer"],
                "explanation": ref.get("explanation"),
            })
    return pairs
