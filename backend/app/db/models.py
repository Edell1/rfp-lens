from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class DocumentState(StrEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    OCR_REQUIRED = "ocr_required"


class ReviewState(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EDITED = "edited"


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class RequirementCategory(StrEnum):
    ELIGIBILITY = "eligibility"
    EXCLUSION = "exclusion"
    SCHEDULE = "schedule"
    BUDGET = "budget"
    SUBMISSION = "submission"
    TECHNICAL_GOAL = "technical_goal"
    QUANTITATIVE_TARGET = "quantitative_target"
    EVALUATION = "evaluation"
    OTHER = "other"


class Importance(StrEnum):
    REQUIRED = "required"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplianceStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    NOT_APPLICABLE = "not_applicable"


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


document_state_type = SqlEnum(
    DocumentState, name="document_state", values_callable=_enum_values
)
review_state_type = SqlEnum(
    ReviewState, name="review_state", values_callable=_enum_values
)
job_state_type = SqlEnum(JobState, name="job_state", values_callable=_enum_values)
requirement_category_type = SqlEnum(
    RequirementCategory, name="requirement_category", values_callable=_enum_values
)
importance_type = SqlEnum(
    Importance, name="importance", values_callable=_enum_values
)
compliance_status_type = SqlEnum(
    ComplianceStatus, name="compliance_status", values_callable=_enum_values
)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)

    projects: Mapped[list[Project]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", passive_deletes=True
    )


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    owner: Mapped[User] = relationship(back_populates="projects")
    documents: Mapped[list[Document]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    analysis_jobs: Mapped[list[AnalysisJob]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    requirements: Mapped[list[Requirement]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    compliance_items: Mapped[list[ComplianceItem]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_project_created_at", "project_id", "created_at"),
        Index("ix_documents_project_state", "project_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    state: Mapped[DocumentState] = mapped_column(
        document_state_type, default=DocumentState.UPLOADED, nullable=False
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="documents")
    blocks: Mapped[list[DocumentBlockRecord]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    analysis_jobs: Mapped[list[AnalysisJob]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    requirements: Mapped[list[Requirement]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class DocumentBlockRecord(Base):
    __tablename__ = "document_blocks"
    __table_args__ = (
        UniqueConstraint("document_id", "block_id", name="uq_document_blocks_block_id"),
        Index("ix_document_blocks_document_order", "document_id", "order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    block_id: Mapped[str] = mapped_column(String(160), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    block_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="blocks")
    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="document_block",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AnalysisJob(TimestampMixin, Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state: Mapped[JobState] = mapped_column(
        job_state_type, default=JobState.QUEUED, nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    provider_usage: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="analysis_jobs")
    document: Mapped[Document] = relationship(back_populates="analysis_jobs")
    requirements: Mapped[list[Requirement]] = relationship(
        back_populates="analysis_job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Requirement(TimestampMixin, Base):
    __tablename__ = "requirements"
    __table_args__ = (
        Index("ix_requirements_project_created_at", "project_id", "created_at"),
        Index(
            "ix_requirements_analysis_review_state",
            "analysis_job_id",
            "review_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    analysis_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[RequirementCategory] = mapped_column(
        requirement_category_type, nullable=False
    )
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    review_state: Mapped[ReviewState] = mapped_column(
        review_state_type, default=ReviewState.PENDING, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="requirements")
    document: Mapped[Document] = relationship(back_populates="requirements")
    analysis_job: Mapped[AnalysisJob] = relationship(back_populates="requirements")
    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="requirement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    compliance_item: Mapped[ComplianceItem | None] = relationship(
        back_populates="requirement",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_block_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_blocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    requirement: Mapped[Requirement] = relationship(back_populates="evidence")
    document_block: Mapped[DocumentBlockRecord] = relationship(back_populates="evidence")


class ComplianceItem(TimestampMixin, Base):
    __tablename__ = "compliance_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    importance: Mapped[Importance] = mapped_column(
        importance_type, default=Importance.REQUIRED, nullable=False
    )
    proposal_section: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    owner_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[ComplianceStatus] = mapped_column(
        compliance_status_type, default=ComplianceStatus.NOT_STARTED, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="compliance_items")
    requirement: Mapped[Requirement] = relationship(back_populates="compliance_item")
