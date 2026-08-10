import hashlib

from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

engine = create_engine("sqlite:///./exam.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def _hash_subject_name(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    code = Column(String, nullable=False, unique=True)  # internal only, never returned via API
    exams = relationship("Exam", back_populates="subject", cascade="all, delete-orphan")


class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    name = Column(String, nullable=False)
    exam_file_path = Column(String)
    answer_file_path = Column(String)
    subject = relationship("Subject", back_populates="exams")
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("exam_id", "number", name="uq_exam_question_number"),)

    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    number = Column(String, nullable=False)
    question_text = Column(Text)
    correct_answer = Column(Text)
    explanation = Column(Text)
    exam = relationship("Exam", back_populates="questions")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_subject(db: Session, name: str) -> Subject:
    subject = db.query(Subject).filter_by(name=name).first()
    if subject is None:
        subject = Subject(name=name, code=_hash_subject_name(name))
        db.add(subject)
        db.flush()
    return subject
