import tempfile
from pathlib import Path
import pypdfium2 as pdfium
import glob

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .src.db import Exam, Question, Subject, get_db, get_or_create_subject, init_db
from .src.llm import grade_pairs, STRUCTURE_PROMPT_DICT, GRADE_PROMPT_DICT, _chat_json
from .src.matching import merge_by_number, pair_questions
from .src.ocr import run_mineru
from .src.storage import new_preview_id, promote_to_exam,\
    save_upload_pending_exam, save_upload_pending_page,\
    read_pending_page, save_upload_pending_question, exam_dir

app = FastAPI(title="Exam Grading Service")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()

class ConfirmExamRequest(BaseModel):
    preview_id: str
    subject_name: str
    exam_name: str
    num_questions : int


class StudentAnswer(BaseModel):
    number: str
    solution: str | None = None


class GradeRequest(BaseModel):
    exam_id: int
    questions: list[StudentAnswer]

@app.get("/subjects")
def list_subjects(db: Session = Depends(get_db)):
    return [{"id": s.id, "name": s.name} for s in db.query(Subject).all()]


@app.get("/subjects/{subject_id}/exams")
def list_exams(subject_id: int, db: Session = Depends(get_db)):
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(404, "subject not found")
    return [{"id": e.id, "name": e.name} for e in subject.exams]


@app.post("/exams/save")
def save_exam(
    subject_name: str = Form(...),
    exam_name: str = Form(...),
    exam_file: UploadFile = File(...),
    answer_file: UploadFile = File(...)
):
    """OCR + structure a exam/answer-key pair without touching the DB yet."""
    preview_id = new_preview_id()
    exam_path = save_upload_pending_exam(preview_id, "exam", exam_file.filename, exam_file.file.read())
    answer_path = save_upload_pending_exam(preview_id, "answer", answer_file.filename, answer_file.file.read())

    exam_pdf = pdfium.PdfDocument(exam_path)
    answer_pdf = pdfium.PdfDocument(answer_path)
    for exam_index, exam_page in enumerate(exam_pdf):
        save_upload_pending_page(preview_id, "exam", exam_index, exam_page)
    for answer_index, answer_page in enumerate(answer_pdf):
        save_upload_pending_page(preview_id, "answer", answer_index, answer_page)
    return {
        "preview_id" : preview_id,
        "subject_name" : subject_name,
        "exam_name" : exam_name
    }

@app.post("/exams/crop")
def crop_exam(
    preview_id : str = Form(...),
    field : str = Form(...),
    page_index : int = Form(...),
    x : int = Form(...),
    y : int = Form(...),
    w : int = Form(...),
    h : int = Form(...)
):
    if field not in ['exam', 'answer']:
        raise HTTPException(400, "Wrong query : field is nor exam, answer")
    base_image = read_pending_page(preview_id)
    box = [x, y, x + w, y + h]
    crop_image = base_image.crop(box)
    save_upload_pending_question(preview_id, "field", page_index, crop_image)

def structure_questions(exam_id : int, number : int) -> Question:
    root_path = exam_dir(exam_id)
    question_path = root_path / "questions" / f'exam_{number}.png'
    answer_path   = root_path / "questions" / f'answer_{number}.png'

    question_text = run_mineru(question_path)
    answer_text   = run_mineru(answer_path)
    return Question(
        exam_id = exam_id,
        number = number,
        question_file_path = question_path,
        answer_file_path   = answer_path,
        question_text  = question_text,
        answer_text    = answer_text
    )
    


@app.post("/exams/confirm")
def confirm_exam(payload: ConfirmExamRequest, db: Session = Depends(get_db)):
    """Persist a previewed exam, using whatever edits the user made to the draft."""

    subject = get_or_create_subject(db, payload.subject_name)
    exam = Exam(subject_id=subject.id, name=payload.exam_name, num_questions=payload.num_questions)
    db.add(exam)
    db.flush()
    try:
        paths = promote_to_exam(payload.preview_id, exam.id)
    except FileNotFoundError:
        db.rollback()
        raise HTTPException(400, "preview not found or already confirmed")

    exam.exam_file_path = paths.get("exam")
    exam.answer_file_path = paths.get("answer")

    for index in range(payload.num_questions):
        db.add(structure_questions(exam.id, index))
    db.commit()
    return {"exam_id": exam.id}


@app.put("/exams/{exam_id}/questions/{number}")
def set_answer(
    exam_id: int,
    number: str,
    answer_text: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """Manually fill in or correct one question's answer after registration."""
    if not db.get(Exam, exam_id):
        raise HTTPException(404, "exam not found")

    question = db.query(Question).filter_by(exam_id=exam_id, number=number).first()
    if question is None:
        question = Question(exam_id=exam_id, number=number)
        db.add(question)
    db.answer_text = answer_text
    db.commit()
    return {"exam_id": exam_id, "number": number, "answer_text" : answer_text}


@app.post("/transcribe")
def transcribe(number : int = File(...), file: UploadFile = File(...)):
    """OCR a student's solved-exam photo into per-question answers. DB-independent."""
    suffix = Path(file.filename or "").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        text = run_mineru(tmp.name)
    return {"questions": StudentAnswer(
        number = number,
        solution = text
    )}


@app.post("/grade")
def grade(payload: GradeRequest, db: Session = Depends(get_db)):
    """Grade a previously-transcribed submission against a stored exam."""
    exam = db.get(Exam, payload.exam_id)
    if not exam:
        raise HTTPException(404, "exam not found")

    reference = {
        q.number: q.answer_text
        for q in exam.questions
    }
    student_questions = [q.model_dump() for q in payload.questions]
    pairs = pair_questions(student_questions, reference)
    results = grade_pairs(pairs)
    return {"exam_id": payload.exam_id, "results": results}


@app.get("/")
def serve_frontend():
    return FileResponse("./app/static/index.html")
