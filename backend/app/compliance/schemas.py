from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.db.models import (
    ComplianceStatus,
    Importance,
    RequirementCategory,
    ReviewState,
)


class EvidenceResponse(BaseModel):
    id: UUID
    block_id: str
    quote: str
    verified: bool
    locator: dict[str, object]


class RequirementResponse(BaseModel):
    id: UUID
    project_id: UUID
    document_id: UUID
    text: str
    category: RequirementCategory
    mandatory: bool
    confidence: str
    review_state: ReviewState
    evidence: list[EvidenceResponse]
    created_at: datetime
    updated_at: datetime


class RequirementPatch(BaseModel):
    updated_at: datetime
    text: str | None = Field(default=None, min_length=3, max_length=1000)
    review_state: ReviewState | None = None
    confirm_unverified: bool = False

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Requirement text must contain at least 3 characters")
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> "RequirementPatch":
        if self.text is None and self.review_state is None:
            raise ValueError("At least one change is required")
        return self


class ComplianceResponse(BaseModel):
    id: UUID
    requirement_id: UUID
    requirement_text: str
    category: RequirementCategory
    mandatory: bool
    evidence_quote: str
    source_location: str
    importance: Importance
    proposal_section: str
    owner_note: str
    status: ComplianceStatus
    created_at: datetime
    updated_at: datetime


class CompliancePatch(BaseModel):
    updated_at: datetime
    importance: Importance | None = None
    proposal_section: str | None = Field(default=None, max_length=255)
    owner_note: str | None = Field(default=None, max_length=5000)
    status: ComplianceStatus | None = None

    @model_validator(mode="after")
    def require_change(self) -> "CompliancePatch":
        if all(
            value is None
            for value in (
                self.importance,
                self.proposal_section,
                self.owner_note,
                self.status,
            )
        ):
            raise ValueError("At least one change is required")
        return self
