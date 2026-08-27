from app.overview.prompt import PROMPT_VERSION
from app.overview.types import (
    RequirementSummaryInput,
    SummaryBatch,
    SummaryHighlight,
    SummaryUsage,
)


class FakeSummaryProvider:
    def summarize(
        self, requirements: list[RequirementSummaryInput]
    ) -> tuple[SummaryBatch, SummaryUsage]:
        grouped: dict = {}
        for item in requirements:
            grouped.setdefault(item.category, []).append(item)
        highlights = [
            SummaryHighlight(
                category=category,
                headline=items[0].text[:120],
                detail=f"연결된 요구사항 {len(items)}건 · 원문 근거를 확인하세요.",
                requirement_ids=[item.id for item in items[:20]],
            )
            for category, items in grouped.items()
        ]
        return SummaryBatch(highlights=highlights), SummaryUsage(
            provider="fake",
            model="synthetic-summary-v1",
            prompt_version=PROMPT_VERSION,
        )
