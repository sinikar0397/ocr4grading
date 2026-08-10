import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .src.db import Exam, Question, Subject, get_db, get_or_create_subject, init_db
from .src.llm import grade_pairs, structure_questions
from .src.matching import merge_by_number, pair_questions
from .src.ocr import run_mineru
from .src.storage import new_preview_id, promote_to_exam, save_upload

app = FastAPI(title="Exam Grading Service")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


class QuestionDraft(BaseModel):
    number: str
    question_text: str | None = None
    answer: str | None = None
    explanation: str | None = None


class ConfirmExamRequest(BaseModel):
    preview_id: str
    subject_name: str
    exam_name: str
    questions: list[QuestionDraft]


class StudentQuestion(BaseModel):
    number: str
    answer: str | None = None
    solution: str | None = None


class GradeRequest(BaseModel):
    exam_id: int
    questions: list[StudentQuestion]


@app.get("/subjects")
def list_subjects(db: Session = Depends(get_db)):
    return [{"id": s.id, "name": s.name} for s in db.query(Subject).all()]


@app.get("/subjects/{subject_id}/exams")
def list_exams(subject_id: int, db: Session = Depends(get_db)):
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(404, "subject not found")
    return [{"id": e.id, "name": e.name} for e in subject.exams]


@app.post("/exams/preview")
def preview_exam(
    subject_name: str = Form(...),
    exam_name: str = Form(...),
    exam_file: UploadFile = File(...),
    answer_file: UploadFile = File(...),
):
    """OCR + structure a exam/answer-key pair without touching the DB yet."""
    preview_id = new_preview_id()
    exam_path = save_upload(preview_id, "exam", exam_file.filename, exam_file.file.read())
    answer_path = save_upload(preview_id, "answer", answer_file.filename, answer_file.file.read())

    exam_questions = structure_questions(run_mineru(str(exam_path)))
    answer_questions = structure_questions(run_mineru(str(answer_path)))
    questions = merge_by_number(exam_questions, answer_questions)

    return {
        "preview_id": preview_id,
        "subject_name": subject_name,
        "exam_name": exam_name,
        "questions": questions,
    }


@app.post("/exams/confirm")
def confirm_exam(payload: ConfirmExamRequest, db: Session = Depends(get_db)):
    """Persist a previewed exam, using whatever edits the user made to the draft."""
    subject = get_or_create_subject(db, payload.subject_name)
    exam = Exam(subject_id=subject.id, name=payload.exam_name)
    db.add(exam)
    db.flush()

    try:
        paths = promote_to_exam(payload.preview_id, exam.id)
    except FileNotFoundError:
        db.rollback()
        raise HTTPException(400, "preview not found or already confirmed")

    exam.exam_file_path = paths.get("exam")
    exam.answer_file_path = paths.get("answer")

    for q in payload.questions:
        db.add(Question(
            exam_id=exam.id,
            number=q.number,
            question_text=q.question_text,
            correct_answer=q.answer,
            explanation=q.explanation,
        ))
    db.commit()
    return {"exam_id": exam.id}


@app.put("/exams/{exam_id}/questions/{number}")
def set_answer(
    exam_id: int,
    number: str,
    correct_answer: str = Form(...),
    explanation: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """Manually fill in or correct one question's answer after registration."""
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


@app.post("/transcribe")
def transcribe(file: UploadFile = File(...)):
    """OCR a student's solved-exam photo into per-question answers. DB-independent."""
    suffix = Path(file.filename or "").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        text = run_mineru(tmp.name)
    return {"questions": structure_questions(text)}


@app.post("/grade")
def grade(payload: GradeRequest, db: Session = Depends(get_db)):
    """Grade a previously-transcribed submission against a stored exam."""
    exam = db.get(Exam, payload.exam_id)
    if not exam:
        raise HTTPException(404, "exam not found")

    reference = {
        q.number: {"correct_answer": q.correct_answer, "explanation": q.explanation}
        for q in exam.questions
    }
    student_questions = [q.model_dump() for q in payload.questions]
    pairs = pair_questions(student_questions, reference)
    results = grade_pairs(pairs)
    return {"exam_id": payload.exam_id, "results": results}


@app.get("/")
def serve_frontend():
    return FileResponse("./app/static/index.html")
