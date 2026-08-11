# hackertoni — 시험지 OCR 채점 서비스

학생이 자신이 푼 시험지 사진을 올리면 OCR로 문항별 풀이를 정리하고, DB에 등록된 시험지/정답지와 대조해 LLM으로 채점·첨삭해주는 서비스.

## 플로우

1. **시험 등록**: 과목명 + 시험명 + 시험지 파일 + 정답지 파일을 업로드하면 MinerU OCR → LLM이 문항 번호 단위로 구조화 → 사용자가 미리보기 화면에서 확인/수정 → 확정하면 DB에 저장
2. **학생 채점**: 학생이 자기가 푼 시험지 사진을 올리면 OCR + LLM 구조화만 먼저 수행(DB와 무관, 이 시점엔 저장 안 함) → 응시한 시험을 DB에서 선택 → 저장된 정답/해설과 대조해 LLM이 문항별로 정답 여부와 피드백을 생성

## 아키텍처

```
app/
  main.py           FastAPI 엔드포인트
  src/
    db.py           SQLAlchemy 모델 (Subject / Exam / Question), SQLite(exam.db)에 영구 저장
    storage.py       업로드 원본 파일 저장 (미리보기 시 임시 위치 → 확정 시 data/exams/<id>/로 이동)
    preprocess.py    사진 입력 자동 기울어짐 보정 (OpenCV)
    ocr.py           MinerU CLI 래퍼 (PDF/이미지 → markdown 텍스트)
    llm.py           Gemini API 호출 (문항 구조화, 채점/첨삭)
    matching.py      시험지/정답지 병합, 학생 답안-DB 정답 매칭 (순수 로직)
  static/            프론트엔드 (index / exam_adding / grading / answer_adding)
```

- DB: SQLite 파일(`exam.db`)로 서버 재시작해도 영구 보존
- 원본 파일(시험지/정답지 PDF·이미지)은 `data/exams/<exam_id>/` 아래에 저장, 경로만 DB에 기록
- OCR은 [MinerU](https://github.com/opendatalab/mineru)를 서브프로세스로 호출. 문항 인식(번호별로 나누기)은 OCR이 아니라 LLM이 텍스트를 보고 구조화
- LLM은 Gemini API를 OpenAI 호환 엔드포인트로 호출 (`openai` SDK 그대로 사용, `base_url`만 Gemini로 지정)
- 한 페이지에 여러 문항이 섞여 있을 때의 박스 감지/수동 그루핑 UI는 현재 범위에서 의도적으로 제외됨 (추후 별도 작업)

## 기술 스택

- Python 3.11, FastAPI, SQLAlchemy(SQLite)
- MinerU (OCR), OpenCV (deskew)
- Gemini API (LLM, OpenAI SDK 호환 엔드포인트로 호출)
- 프론트엔드: 순수 HTML + vanilla JS (프레임워크 없음)

## 설치

프로젝트 전용 conda 환경 `ocrenv`를 사용한다.

```bash
conda create -n ocrenv python=3.11
conda activate ocrenv
pip install -r requirements.txt
```

MinerU 모델 가중치는 최초 1회 별도로 받아야 한다 (수백MB~2GB, Mac은 GPU가 없으므로 가벼운 pipeline 백엔드용만 받으면 충분):

```bash
mineru-models-download -m pipeline
```

## 환경변수

| 변수 | 설명 |
|---|---|
| `GEMINI_API_KEY` | 필수. LLM 호출(문항 구조화, 채점)에 사용 |
| `GRADING_MODEL` | 선택. 기본값 `gemini-flash-latest` (현재 세대 Flash 모델로 자동 연결되는 별칭) |

## 실행

```bash
uvicorn app.main:app --reload
```

`http://127.0.0.1:8000/` 접속하면 프론트엔드 진입점이 뜬다.

## API

| Method | Path | 설명 |
|---|---|---|
| GET | `/subjects` | 과목 목록 |
| GET | `/subjects/{subject_id}/exams` | 과목별 시험 목록 |
| POST | `/exams/preview` | 시험지+정답지 업로드 → OCR/구조화 미리보기 (DB 미반영) |
| POST | `/exams/confirm` | 미리보기 결과(수정 가능)를 DB에 확정 저장 |
| PUT | `/exams/{exam_id}/questions/{number}` | 특정 문항 정답/해설 수동 입력·수정 |
| POST | `/transcribe` | 학생 답안 사진 OCR → 문항별 구조화 (DB 무관) |
| POST | `/grade` | `/transcribe` 결과 + `exam_id`로 채점·첨삭 |

## 테스트

프레임워크 없이 assert 기반 스크립트로 순수 로직만 검증한다 (LLM/OCR 호출 없이 실행 가능).

```bash
python test_matching.py
python test_preprocess.py
```

## 알려진 제한사항

- `GEMINI_API_KEY`가 없으면 `/exams/preview`, `/transcribe`, `/grade`는 호출 시 에러
- LLM 호출 실패(레이트리밋, 타임아웃 등)에 대한 재시도 로직 없음
- deskew는 컨투어 기반 자동 보정이라 배경이 복잡하거나 종이 경계가 흐리면 실패할 수 있음 (실패 시 원본 그대로 사용)
- 한 페이지에 여러 문항이 섞인 경우의 박스 지정/그루핑 기능 없음
