from app.analysis.fake_provider import FakeRequirementProvider
from app.analysis.openai_provider import OpenAIRequirementProvider
from app.analysis.provider import AnalysisService, RequirementProvider
from app.core.config import Settings


def create_requirement_provider(settings: Settings) -> RequirementProvider:
    if settings.ai_provider == "fake":
        if settings.environment not in {"test", "demo"}:
            raise RuntimeError("The fake AI provider is allowed only in test or demo")
        return FakeRequirementProvider()
    if settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("RFP_LENS_OPENAI_API_KEY is required")
        return OpenAIRequirementProvider(
            api_key=settings.openai_api_key, model=settings.openai_model
        )
    raise RuntimeError(f"Unsupported AI provider: {settings.ai_provider}")


__all__ = ["AnalysisService", "create_requirement_provider"]
