import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .db import Exam, Question, get_db, init_db
from .llm import grade_pairs, structure_questions
from .matching import pair_questions
from .ocr import run_mineru

app = FastAPI(title="Exam Grading Service")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def _save_upload(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        return tmp.name


@app.post("/exams")
def create_exam(name: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a reference exam/answer-key PDF and store its per-question answers."""
    path = _save_upload(file)
    text = run_mineru(path)
    questions = structure_questions(text)

    exam = Exam(name=name)
    db.add(exam)
    db.flush()
    for q in questions:
        db.add(Question(
            exam_id=exam.id,
            number=str(q["number"]),
            correct_answer=q.get("answer"),
            explanation=q.get("explanation"),
        ))
    db.commit()
    return {"exam_id": exam.id, "questions": questions}


@app.put("/exams/{exam_id}/questions/{number}")
def set_answer(
    exam_id: int,
    number: str,
    correct_answer: str = Form(...),
    explanation: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """Manually fill in an answer the reference DB didn't have."""
    if not db.get(Exam, exam_id):
        raise HTTPException(404, "exam not found")

    question = db.query(Question).filter_by(exam_id=exam_id, number=number).first()
    if question is None:
        question = Question(exam_id=exam_id, number=number)
        db.add(question)
    question.correct_answer = correct_answer
    question.explanation = explanation
    db.commit()
    return {"exam_id": exam_id, "number": number, "correct_answer": correct_answer}


@app.post("/grade")
def grade(exam_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a photo of a student's solved exam and grade it against the stored exam."""
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "exam not found")

    path = _save_upload(file)
    text = run_mineru(path)
    student_questions = structure_questions(text)

    reference = {
        q.number: {"correct_answer": q.correct_answer, "explanation": q.explanation}
        for q in exam.questions
    }
    pairs = pair_questions(student_questions, reference)
    results = grade_pairs(pairs)
    return {"exam_id": exam_id, "results": results}
