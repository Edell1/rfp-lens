from app.analysis.prompt import PROMPT_VERSION
from app.analysis.types import AnalysisChunk, ExtractedRequirement, ExtractionUsage
from app.db.models import RequirementCategory


class FakeRequirementProvider:
    """Deterministic provider for tests and the local demo environment."""

    phrases = (
        (
            "중소기업만 신청 가능",
            "중소기업만 신청 가능",
            RequirementCategory.ELIGIBILITY,
            True,
        ),
        (
            "정부출연금은 총 5억원 이내이다.",
            "정부출연금은 5억원 이내이다",
            RequirementCategory.BUDGET,
            True,
        ),
    )

    def extract(
        self, chunks: list[AnalysisChunk]
    ) -> tuple[list[ExtractedRequirement], ExtractionUsage]:
        requirements: list[ExtractedRequirement] = []
        for chunk in chunks:
            for block in chunk.blocks:
                for quote, requirement, category, mandatory in self.phrases:
                    if quote in block.text:
                        requirements.append(
                            ExtractedRequirement(
                                requirement=requirement,
                                category=category,
                                mandatory=mandatory,
                                source_block_id=block.block_id,
                                evidence_quote=quote,
                                confidence="high",
                            )
                        )
        return requirements, ExtractionUsage(
            provider="fake",
            model="synthetic-fixture-v1",
            prompt_version=PROMPT_VERSION,
        )
