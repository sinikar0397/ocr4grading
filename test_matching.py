from app.matching import pair_questions


def test_missing_reference_is_flagged():
    result = pair_questions([{"number": "1", "answer": "3", "solution": "1+2=3"}], {})
    assert result[0]["status"] == "missing_reference"


def test_present_reference_is_paired_for_grading():
    student = [{"number": "1", "answer": "3", "solution": "1+2=3"}]
    reference = {"1": {"correct_answer": "3", "explanation": "덧셈"}}
    result = pair_questions(student, reference)
    assert result[0]["status"] == "to_grade"
    assert result[0]["correct_answer"] == "3"


def test_blank_correct_answer_counts_as_missing():
    student = [{"number": "2", "answer": "x"}]
    reference = {"2": {"correct_answer": "", "explanation": None}}
    result = pair_questions(student, reference)
    assert result[0]["status"] == "missing_reference"


if __name__ == "__main__":
    test_missing_reference_is_flagged()
    test_present_reference_is_paired_for_grading()
    test_blank_correct_answer_counts_as_missing()
    print("OK")
