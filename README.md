# hackertoni — 시험지 OCR 채점 서비스

학생이 자신이 푼 시험지 사진을 올리면 OCR로 문항별 풀이를 정리하고, DB에 등록된 시험지/정답지와 대조해 LLM으로 채점·첨삭해주는 서비스.

## 플로우

1. **시험 등록** (선생님, `exam_adding.html`)
   - 과목명 + 시험명 + 총 문제 수 + 시험지 PDF + 정답지 PDF 업로드 → PDF를 페이지별 이미지로 분리
   - 문항 하나하나마다: 좌우 화살표로 페이지를 넘겨가며 해당 문항이 있는 페이지를 찾고, 이미지 위에서 드래그로 영역을 지정해서 크롭
   - 발문과 문제 본문이 페이지상 떨어져 있으면 "이 영역 추가"를 여러 번 눌러 서로 다른 영역(다른 페이지 포함)을 하나의 문항 이미지로 이어붙일 수 있음
   - 모든 문항의 영역 지정이 끝나면 확정 → 서버가 각 문항 이미지를 MinerU로 OCR해서 DB에 저장 (문항 본문 `question_text`, 모범답안 원문 `answer_text`)
   - 등록 후 특정 문항의 답이 잘못 인식됐으면 수동으로 고칠 수 있음(`answer_adding.html` — 단, 아래 [알려진 제한사항](#알려진-제한사항) 참고)
2. **학생 채점** (`grading.html`)
   - 과목/시험 선택 (DB에 저장된 `num_questions`만큼 문항별 입력 칸이 생성됨)
   - 문항마다: 사진을 새로 찍어 올리거나(문제별 개별 촬영), 이미 올린 사진에서 영역만 새로 지정(한 장에 여러 문항이 있는 경우) — 어느 쪽이든 브라우저에서 크롭한 이미지를 서버로 보내 OCR
   - 모든 문항이 전사되면 채점 요청 → DB에 저장된 정답 원문과 학생 풀이를 LLM에 보내 문항별로 정답 여부(`is_correct`)와 피드백(`feedback`)을 생성

## 아키텍처

```
app/
  main.py           FastAPI 엔드포인트
  src/
    db.py           SQLAlchemy 모델 (Subject / Exam / Question), SQLite(exam.db)에 영구 저장
    storage.py       업로드 원본·페이지·문항 크롭 이미지 저장 (미리보기 시 임시 위치 → 확정 시 data/exams/<id>/로 이동)
    preprocess.py    사진 입력 자동 기울어짐 보정 (OpenCV)
    ocr.py           MinerU CLI 래퍼 (PDF/이미지 → markdown 텍스트)
    llm.py           Gemini API 호출 (채점 판정 is_correct / 첨삭 feedback, 문항당 각각 1회씩 호출)
    matching.py      학생 답안-DB 정답 매칭 (순수 로직)
  static/            프론트엔드 (index / exam_adding / grading / answer_adding), 프레임워크 없이 vanilla JS
```

- DB: SQLite 파일(`exam.db`)로 서버 재시작해도 영구 보존. `Question`은 문항 본문(`question_text`)과 모범답안 원문(`answer_text`) 딱 두 텍스트 필드만 가짐 — 정답/해설을 등록 시점에 미리 구조화하지 않고, 채점 시점에 LLM이 원문을 보고 직접 판단
- 원본 파일(시험지/정답지 PDF, 페이지 이미지, 문항별 크롭 이미지)은 `data/exams/<exam_id>/` 아래에 저장, 경로만 DB에 기록
- 시험 등록 시 크롭은 `page_index`(어느 페이지에서 잘랐는지)와 `number`(몇 번 문항인지)가 분리되어 있어, 한 페이지에 여러 문항이 있어도 문제없이 각각 크롭 가능. 같은 문항에 크롭을 여러 번 하면 덮어쓰지 않고 세로로 이어붙임(발문/문제 분리 대응)
- OCR은 [MinerU](https://github.com/opendatalab/mineru)를 서브프로세스로 호출. 문항 인식(어디부터 어디까지가 한 문항인지)은 OCR/LLM이 아니라 사람이 크롭으로 직접 지정
- LLM은 Gemini API를 OpenAI 호환 엔드포인트로 호출 (`openai` SDK 그대로 사용, `base_url`만 Gemini로 지정). 채점 1문항당 정답 판정 1회 + 첨삭 1회, 총 2회 호출

## 기술 스택

- Python 3.11+, FastAPI, SQLAlchemy(SQLite)
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
| `GEMINI_API_KEY` | `/grade`(채점 판정·첨삭)에 사용. 시험 등록·크롭·전사(OCR)는 이 키 없이도 동작 |
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
| GET | `/subjects/{subject_id}/exams` | 과목별 시험 목록 (`num_questions` 포함) |
| POST | `/exams/save` | 시험지+정답지 PDF 업로드 → 페이지별 이미지로 분리, `preview_id`/페이지 수 반환 (DB 미반영) |
| GET | `/exams/preview/{preview_id}/pages/{field}/{page_index}` | 업로드된 시험지(`exam`)/정답지(`answer`)의 특정 페이지 이미지 서빙 (크롭 UI용) |
| POST | `/exams/crop` | 페이지 `page_index`에서 문항 `number`의 영역(x,y,w,h)을 잘라 저장. 같은 문항에 여러 번 호출하면 이어붙임 |
| POST | `/exams/confirm` | 크롭된 문항 이미지들을 OCR해서 DB에 확정 저장 |
| PUT | `/exams/{exam_id}/questions/{number}` | 특정 문항 모범답안(`answer_text`) 수동 입력·수정 |
| POST | `/transcribe` | 학생 답안 사진(또는 크롭된 이미지) 1장 + 문항 번호 → OCR (DB 무관, 문항 하나씩 처리) |
| POST | `/grade` | 전사된 문항 답안 배열 + `exam_id`로 채점(`is_correct`)·첨삭(`feedback`) |

## 테스트

프레임워크 없이 assert 기반 스크립트로 순수 로직만 검증한다 (LLM/OCR 호출 없이 실행 가능).

```bash
python test_preprocess.py
```

`test_matching.py`는 `matching.py`가 리팩터링되면서 (`merge_by_number` 제거, `pair_questions`의 참조 형식이 `dict[str, dict]` → `dict[str, str]`로 변경) 깨진 상태다 — 실행하면 import 단계에서 실패한다. 현재 스키마 기준으로 다시 작성 필요.

## 알려진 제한사항

- `answer_adding.html`(문항 정답 수동 입력 화면)은 아직 예전 스키마(`correct_answer` + `explanation` 2필드) 기준으로 되어 있어, 지금 백엔드(`answer_text` 1필드)와 폼 필드명이 안 맞음 — 이 화면으로 정답을 고쳐도 반영되지 않는다. 업데이트 필요
- 문항 크롭을 잘못 지정했을 때 초기화(완전히 새로 시작)하는 기능이 없음 — 계속 이어붙이기만 가능
- `GEMINI_API_KEY`가 없으면 `/grade` 호출 시 에러 (등록·전사는 영향 없음)
- LLM 호출 실패(레이트리밋, 타임아웃 등)에 대한 재시도 로직 없음
- 채점은 문항마다 LLM을 2회씩(정답 판정 + 첨삭) 호출하는 구조라, 문항 수가 많으면 지연시간·비용이 그만큼 늘어남 (배치 호출 아님)
- `/exams/confirm`과 `/transcribe`는 MinerU OCR을 요청 처리 중에 동기적으로 실행하므로, 문항 수/사진 크기에 따라 응답이 느릴 수 있음
- deskew는 컨투어 기반 자동 보정이라 배경이 복잡하거나 종이 경계가 흐리면 실패할 수 있음 (실패 시 원본 그대로 사용)
