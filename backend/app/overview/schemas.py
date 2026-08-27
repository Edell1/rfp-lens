from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.models import RequirementCategory, ReviewState, SummaryState
from app.overview.types import OverviewStats, SummaryHighlight, SummaryScope


class OverviewEvidenceResponse(BaseModel):
    quote: str
    verified: bool
    locator: dict[str, object]


class FallbackRequirementResponse(BaseModel):
    id: UUID
    text: str
    category: RequirementCategory
    mandatory: bool
    review_state: ReviewState
    evidence: list[OverviewEvidenceResponse]


class AnalysisOverviewResponse(BaseModel):
    empty: bool = False
    effective_scope: SummaryScope
    summary_state: SummaryState
    stale: bool
    stats: OverviewStats
    category_counts: dict[RequirementCategory, int]
    highlights: list[SummaryHighlight]
    fallback_requirements: list[FallbackRequirementResponse]
    updated_at: datetime | None
