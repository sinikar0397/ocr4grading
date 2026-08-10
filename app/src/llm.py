import json
import os

from openai import OpenAI

MODEL = os.environ.get("GRADING_MODEL", "gemini-flash-latest")

# Gemini exposes an OpenAI-compatible endpoint, so the OpenAI SDK works
# unmodified against it: https://ai.google.dev/gemini-api/docs/openai
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url=GEMINI_BASE_URL)
    return _client


STRUCTURE_PROMPT = """\
너는 시험지 OCR 결과를 문제별로 정리하는 도우미다.
아래는 시험지 또는 답안지를 OCR한 markdown 텍스트다.
문제 번호 단위로 나누어 다음 JSON 형식으로만 답하라:

{"questions": [
  {"number": "문제 번호 (문자열)",
   "question_text": "문제 본문/지문 (시험지 OCR인 경우; 없으면 null)",
   "answer": "최종 정답 또는 학생이 적은 최종 답 (없으면 null)",
   "solution": "풀이 과정 (없으면 null)",
   "explanation": "해설/정답 근거 (없으면 null)"}
]}
"""

GRADE_PROMPT = """\
너는 채점 도우미다. 각 문제에 대해 학생의 답/풀이와 정답/해설이 주어진다.
학생의 최종 답이 정답과 실질적으로 같은 의미인지 판단하고, 다를 경우 풀이 과정에서
어디가 틀렸는지 간단히 짚어라. 아래 JSON 형식으로만 답하라:

{"results": [
  {"number": "문제 번호", "is_correct": true/false, "feedback": "한두 문장 피드백"}
]}
"""


def _chat_json(system_prompt: str, payload: str) -> dict:
    client = _get_client()
    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def structure_questions(raw_text: str) -> list[dict]:
    return _chat_json(STRUCTURE_PROMPT, raw_text).get("questions", [])


def grade_pairs(pairs: list[dict]) -> list[dict]:
    to_grade = [p for p in pairs if p["status"] == "to_grade"]
    if not to_grade:
        return pairs

    graded = _chat_json(GRADE_PROMPT, json.dumps(to_grade, ensure_ascii=False)).get("results", [])
    graded_by_number = {g["number"]: g for g in graded}

    merged = []
    for p in pairs:
        g = graded_by_number.get(p["number"]) if p["status"] == "to_grade" else None
        merged.append({**p, "is_correct": g.get("is_correct"), "feedback": g.get("feedback")} if g else p)
    return merged
