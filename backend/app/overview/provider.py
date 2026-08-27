from typing import Protocol

from app.core.config import Settings
from app.overview.fake_provider import FakeSummaryProvider
from app.overview.local_provider import LocalSummaryProvider
from app.overview.openai_provider import OpenAISummaryProvider
from app.overview.types import RequirementSummaryInput, SummaryBatch, SummaryUsage


class SummaryProvider(Protocol):
    def summarize(
        self, requirements: list[RequirementSummaryInput]
    ) -> tuple[SummaryBatch, SummaryUsage]: ...


def create_summary_provider(settings: Settings) -> SummaryProvider:
    if settings.ai_provider == "fake":
        if settings.environment not in {"test", "demo"}:
            raise RuntimeError("The fake AI provider is allowed only in test or demo")
        return FakeSummaryProvider()
    if settings.ai_provider == "local":
        if not settings.local_model:
            raise ValueError("Local summary model is not configured")
        return LocalSummaryProvider(
            base_url=settings.local_base_url, model=settings.local_model
        )
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key is not configured")
    return OpenAISummaryProvider(
        api_key=settings.openai_api_key, model=settings.openai_model
    )
