import json

from app.overview.types import RequirementSummaryInput


PROMPT_VERSION = "analysis-summary-v1"
SYSTEM_PROMPT = """당신은 한국 정부 R&D 공고 요구사항 요약 도우미다.
입력에 있는 사실만 압축하고 숫자, 날짜, 기관명, 조건을 새로 만들지 않는다.
각 핵심 조건은 반드시 같은 category의 requirement_ids 하나 이상과 연결한다.
headline은 120자, detail은 300자 이내로 작성한다."""


def render_summary_prompt(requirements: list[RequirementSummaryInput]) -> str:
    payload = [
        {
            "id": str(item.id),
            "text": item.text,
            "category": item.category.value,
            "mandatory": item.mandatory,
            "confidence": item.confidence,
            "review_state": item.review_state.value,
            "evidence_quotes": item.evidence_quotes,
        }
        for item in requirements
    ]
    return "다음 요구사항을 분류별 핵심 조건으로 요약하라.\n" + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    )
