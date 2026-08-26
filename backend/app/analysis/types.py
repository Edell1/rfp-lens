from typing import Literal

from pydantic import BaseModel, Field

from app.db.models import RequirementCategory, ReviewState
from app.parsing.types import DocumentBlock


class AnalysisChunk(BaseModel, frozen=True):
    chunk_id: str
    blocks: list[DocumentBlock]


class ExtractedRequirement(BaseModel, frozen=True):
    requirement: str = Field(min_length=3, max_length=1000)
    category: RequirementCategory
    mandatory: bool
    source_block_id: str = Field(min_length=1, max_length=160)
    evidence_quote: str = Field(min_length=1, max_length=2000)
    confidence: Literal["high", "medium", "low"]


class ExtractionBatch(BaseModel, frozen=True):
    requirements: list[ExtractedRequirement] = Field(default_factory=list)


class ExtractionUsage(BaseModel, frozen=True):
    provider: str
    model: str
    prompt_version: str
    latency_ms: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class ValidatedEvidence(BaseModel, frozen=True):
    source_block_id: str
    quote: str
    verified: bool


class ValidatedRequirement(BaseModel, frozen=True):
    requirement: str
    category: RequirementCategory
    mandatory: bool
    confidence: Literal["high", "medium", "low"]
    review_state: ReviewState = ReviewState.PENDING
    evidence: list[ValidatedEvidence]


class AnalysisOutcome(BaseModel, frozen=True):
    requirements: list[ValidatedRequirement]
    usage: ExtractionUsage
    total_chunks: int = Field(ge=0)
    failed_chunks: int = Field(ge=0)
