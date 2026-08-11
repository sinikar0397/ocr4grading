from app.src.matching import merge_by_number, pair_questions


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


def test_merge_combines_exam_and_answer_by_number():
    exam_qs = [{"number": "1", "question_text": "1+2=?"}]
    answer_qs = [{"number": "1", "answer": "3", "explanation": "덧셈"}]
    merged = merge_by_number(exam_qs, answer_qs)
    assert merged == [{"number": "1", "question_text": "1+2=?", "answer": "3", "explanation": "덧셈"}]


def test_merge_keeps_side_with_missing_counterpart():
    exam_qs = [{"number": "1", "question_text": "1+2=?"}, {"number": "2", "question_text": "3*3=?"}]
    answer_qs = [{"number": "1", "answer": "3", "explanation": "덧셈"}]
    merged = merge_by_number(exam_qs, answer_qs)
    by_number = {m["number"]: m for m in merged}
    assert by_number["2"]["answer"] is None
    assert by_number["2"]["question_text"] == "3*3=?"


def test_merge_handles_answer_only_number():
    answer_qs = [{"number": "5", "answer": "42", "explanation": None}]
    merged = merge_by_number([], answer_qs)
    assert merged == [{"number": "5", "question_text": None, "answer": "42", "explanation": None}]


if __name__ == "__main__":
    test_missing_reference_is_flagged()
    test_present_reference_is_paired_for_grading()
    test_blank_correct_answer_counts_as_missing()
    test_merge_combines_exam_and_answer_by_number()
    test_merge_keeps_side_with_missing_counterpart()
    test_merge_handles_answer_only_number()
    print("OK")
