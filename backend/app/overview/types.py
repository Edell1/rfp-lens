from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import RequirementCategory, ReviewState


SummaryScope = Literal["all", "reviewed"]
RequestedSummaryScope = Literal["auto", "all", "reviewed"]


class RequirementSummaryInput(BaseModel, frozen=True):
    id: UUID
    text: str
    category: RequirementCategory
    mandatory: bool
    confidence: str
    review_state: ReviewState
    updated_at: datetime
    evidence_quotes: list[str] = Field(default_factory=list)
    evidence_verified: list[bool] = Field(default_factory=list)


class SummaryHighlight(BaseModel, frozen=True):
    category: RequirementCategory
    headline: str = Field(min_length=1, max_length=120)
    detail: str = Field(min_length=1, max_length=300)
    requirement_ids: list[UUID] = Field(min_length=1, max_length=20)


class SummaryBatch(BaseModel, frozen=True):
    highlights: list[SummaryHighlight] = Field(default_factory=list, max_length=30)


class SummaryUsage(BaseModel, frozen=True):
    provider: str
    model: str
    prompt_version: str
    latency_ms: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class OverviewStats(BaseModel, frozen=True):
    total: int
    confirmed_or_edited: int
    pending: int
    rejected: int
    unverified_evidence: int
