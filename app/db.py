from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

engine = create_engine("sqlite:///./exam.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("exam_id", "number", name="uq_exam_question_number"),)

    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    number = Column(String, nullable=False)
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
