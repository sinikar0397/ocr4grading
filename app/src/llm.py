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


"""
{"questions": [
  {"number": "문제 번호 (문자열)",
   "question_text": "문제 본문/지문 (시험지 OCR인 경우; 없으면 null)",
   "answer": "최종 정답 또는 학생이 적은 최종 답 (없으면 null)",
   "solution": "풀이 과정 (없으면 null)",
   "explanation": "해설/정답 근거 (없으면 null)"}
]}
"""

GRADE_PROMPT_DICT = {
    "is_correct" :
"""너는 채점 도우미다.
문제에 대해 문제 내용, 학생의 답(풀이)와 정답(해설)이 주어진다.
학생의 답이 옳은지를 확인하여, true, false 중 하나의 단어로 답하라.""",
    "feedback" :
"""너는 채점 도우미다.
문제에 대해 문제 내용, 학생의 답(풀이)와 정답(해설)이 주어진다.
학생의 풀이 과정과 정답의 풀이 과정이 같은 의미인지, 혹은 학생의 답이
논리적으로 맞는 답인지 판단하고 그러지 못할 경우 풀이 과정에서 어디가
틀렸는지 간단하게 짚어라. 부가적인 내용 없이 해당 내용에 대해 한두문장의 피드백을 반환하라.""",
}


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
    return resp.choices[0].message.content


def grade_pairs(pairs: list[dict]) -> list[dict]:
    to_grade = [p for p in pairs if p["status"] == "to_grade"]
    if not to_grade:
        return pairs


    graded = [
        {
            "number" : g["number"],
            "is_correct" : _chat_json(GRADE_PROMPT_DICT["is_correct"], json.dumps(g)),
            "feedback" : _chat_json(GRADE_PROMPT_DICT["feedback"], json.dumps(g))
        }
        for g in to_grade
    ]
    graded_by_number = {g["number"]: g for g in graded}

    merged = []
    for p in pairs:
        g = graded_by_number.get(p["number"]) if p["status"] == "to_grade" else None
        merged.append({**p, "is_correct": g.get("is_correct"), "feedback": g.get("feedback")} if g else p)
    return merged
