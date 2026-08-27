from hashlib import sha256
import json
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    AnalysisSummary,
    Evidence,
    Project,
    Requirement,
    RequirementCategory,
    ReviewState,
    SummaryScope as DbSummaryScope,
    SummaryState,
)
from app.overview.prompt import PROMPT_VERSION
from app.overview.types import (
    OverviewStats,
    RequestedSummaryScope,
    RequirementSummaryInput,
    SummaryHighlight,
    SummaryScope,
)


REVIEWED_STATES = {ReviewState.CONFIRMED, ReviewState.EDITED}
CORE_CATEGORIES = (
    RequirementCategory.ELIGIBILITY,
    RequirementCategory.BUDGET,
    RequirementCategory.SCHEDULE,
    RequirementCategory.SUBMISSION,
    RequirementCategory.EVALUATION,
    RequirementCategory.TECHNICAL_GOAL,
)


def lock_project_for_summary(db: Session, project_id) -> None:
    """Serialize summary cache creation across API and analysis workers."""
    db.execute(select(Project.id).where(Project.id == project_id).with_for_update())


def calculate_stats(requirements: Iterable[RequirementSummaryInput]) -> OverviewStats:
    items = list(requirements)
    return OverviewStats(
        total=len(items),
        confirmed_or_edited=sum(item.review_state in REVIEWED_STATES for item in items),
        pending=sum(item.review_state == ReviewState.PENDING for item in items),
        rejected=sum(item.review_state == ReviewState.REJECTED for item in items),
        unverified_evidence=sum(
            bool(item.evidence_verified) and not all(item.evidence_verified)
            for item in items
        ),
    )


def choose_effective_scope(
    requested: RequestedSummaryScope,
    requirements: Iterable[RequirementSummaryInput],
) -> SummaryScope:
    has_reviewed = any(item.review_state in REVIEWED_STATES for item in requirements)
    if requested == "all":
        return "all"
    if requested == "reviewed" and not has_reviewed:
        return "all"
    return "reviewed" if has_reviewed else "all"


def requirements_in_scope(
    requirements: Iterable[RequirementSummaryInput], scope: SummaryScope
) -> list[RequirementSummaryInput]:
    if scope == "reviewed":
        return [item for item in requirements if item.review_state in REVIEWED_STATES]
    return [item for item in requirements if item.review_state != ReviewState.REJECTED]


def source_fingerprint(requirements: Iterable[RequirementSummaryInput]) -> str:
    source = [
        {
            "id": str(item.id),
            "updated_at": item.updated_at.isoformat(),
            "review_state": item.review_state.value,
        }
        for item in sorted(requirements, key=lambda entry: str(entry.id))
    ]
    return sha256(
        json.dumps(source, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def validate_highlights(
    highlights: Iterable[SummaryHighlight],
    requirements: Iterable[RequirementSummaryInput],
) -> list[SummaryHighlight]:
    category_by_id = {item.id: item.category for item in requirements}
    validated: list[SummaryHighlight] = []
    for highlight in highlights:
        ids = list(
            dict.fromkeys(
                requirement_id
                for requirement_id in highlight.requirement_ids
                if category_by_id.get(requirement_id) == highlight.category
            )
        )
        if ids:
            validated.append(highlight.model_copy(update={"requirement_ids": ids}))
    return validated


def category_counts(
    requirements: Iterable[RequirementSummaryInput],
) -> dict[RequirementCategory, int]:
    counts = {category: 0 for category in RequirementCategory}
    for item in requirements:
        counts[item.category] += 1
    return counts


def load_summary_inputs(
    db: Session, project_id
) -> tuple[list[RequirementSummaryInput], dict]:
    records = list(
        db.scalars(
            select(Requirement)
            .where(Requirement.project_id == project_id)
            .options(
                selectinload(Requirement.evidence).selectinload(
                    Evidence.document_block
                )
            )
            .order_by(Requirement.created_at, Requirement.id)
        )
    )
    inputs = [
        RequirementSummaryInput(
            id=record.id,
            text=record.text,
            category=record.category,
            mandatory=record.mandatory,
            confidence=record.confidence,
            review_state=record.review_state,
            updated_at=record.updated_at,
            evidence_quotes=[evidence.quote for evidence in record.evidence],
            evidence_verified=[evidence.verified for evidence in record.evidence],
        )
        for record in records
    ]
    return inputs, {record.id: record for record in records}


def ensure_summary_cache(
    db: Session,
    project_id,
    scope: SummaryScope,
    fingerprint: str,
) -> tuple[AnalysisSummary, bool, bool]:
    db_scope = DbSummaryScope(scope)
    summary = db.scalar(
        select(AnalysisSummary).where(
            AnalysisSummary.project_id == project_id,
            AnalysisSummary.scope == db_scope,
        )
    )
    if summary is None:
        summary = AnalysisSummary(
            project_id=project_id,
            scope=db_scope,
            state=SummaryState.PENDING,
            prompt_version=PROMPT_VERSION,
            source_fingerprint=fingerprint,
        )
        db.add(summary)
        return summary, True, False
    if summary.source_fingerprint != fingerprint:
        summary.source_fingerprint = fingerprint
        summary.state = SummaryState.PENDING
        summary.error_code = None
        summary.error_message = None
        summary.started_at = None
        summary.completed_at = None
        return summary, True, bool(summary.highlights)
    if (
        summary.state == SummaryState.FAILED
        and summary.error_code == "summary_queue_failed"
    ):
        summary.state = SummaryState.PENDING
        summary.error_code = None
        summary.error_message = None
        return summary, True, bool(summary.highlights)
    stale = bool(summary.highlights) and summary.highlights_fingerprint != fingerprint
    return summary, False, stale
