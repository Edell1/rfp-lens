PROMPT_VERSION = "requirements-v1"

SYSTEM_PROMPT = """당신은 대한민국 정부 R&D 공고문에서 제안서 준수 요구사항을 추출한다.

규칙:
1. 원문에 명시된 요구사항만 추출한다.
2. 누락된 금액, 수치, 일정, 신청 자격을 추론하거나 보완하지 않는다.
3. evidence_quote는 제공된 블록에서 근거 문장을 글자 그대로 복사한다.
4. 직접 인용할 근거가 없으면 해당 항목을 반환하지 않는다.
5. 의무 표현과 권고·예시 표현을 구분하여 mandatory를 정한다.
6. 모든 항목을 제공된 category 열거형 중 하나로 분류한다.
7. source_block_id는 근거가 들어 있는 블록 ID와 정확히 일치해야 한다.
"""


def render_chunk_prompt(chunk_id: str, blocks: list[tuple[str, str]]) -> str:
    rendered = "\n\n".join(
        f"[block_id={block_id}]\n{text}" for block_id, text in blocks
    )
    return f"청크 ID: {chunk_id}\n\n{rendered}"
