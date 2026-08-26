from typing import Protocol

from app.analysis.chunking import chunk_blocks
from app.analysis.types import (
    AnalysisChunk,
    AnalysisOutcome,
    ExtractedRequirement,
    ExtractionUsage,
)
from app.analysis.validator import merge_duplicates, validate_requirement
from app.parsing.types import DocumentBlock


class ProviderFailure(RuntimeError):
    """The provider refused or returned an unusable structured response."""


class RequirementProvider(Protocol):
    def extract(
        self, chunks: list[AnalysisChunk]
    ) -> tuple[list[ExtractedRequirement], ExtractionUsage]: ...


class AnalysisService:
    def __init__(
        self,
        provider: RequirementProvider,
        *,
        max_attempts: int = 3,
        target_chars: int = 12_000,
        hard_max_chars: int = 16_000,
    ) -> None:
        self.provider = provider
        self.max_attempts = max_attempts
        self.target_chars = target_chars
        self.hard_max_chars = hard_max_chars

    def analyze(self, blocks: list[DocumentBlock]) -> AnalysisOutcome:
        chunks = chunk_blocks(
            blocks,
            target_chars=self.target_chars,
            hard_max_chars=self.hard_max_chars,
        )
        validated = []
        failed_chunks = 0
        usages: list[ExtractionUsage] = []

        for chunk in chunks:
            for attempt in range(self.max_attempts):
                try:
                    extracted, usage = self.provider.extract([chunk])
                    usages.append(usage)
                    chunk_blocks_by_id = {
                        block.block_id: block for block in chunk.blocks
                    }
                    validated.extend(
                        validate_requirement(item, chunk_blocks_by_id)
                        for item in extracted
                    )
                    break
                except (TimeoutError, ProviderFailure, ValueError):
                    if attempt + 1 == self.max_attempts:
                        failed_chunks += 1

        if usages:
            first = usages[0]
            usage = ExtractionUsage(
                provider=first.provider,
                model=first.model,
                prompt_version=first.prompt_version,
                latency_ms=sum(item.latency_ms for item in usages),
                input_tokens=sum(item.input_tokens for item in usages),
                output_tokens=sum(item.output_tokens for item in usages),
            )
        else:
            usage = ExtractionUsage(
                provider="unknown", model="unknown", prompt_version="requirements-v1"
            )

        return AnalysisOutcome(
            requirements=merge_duplicates(validated),
            usage=usage,
            total_chunks=len(chunks),
            failed_chunks=failed_chunks,
        )
