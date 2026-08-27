from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import ValidationError

from app.auth.dependencies import CurrentUser, DatabaseSession
from app.db.models import SummaryState
from app.overview.schemas import (
    AnalysisOverviewResponse,
    FallbackRequirementResponse,
    OverviewEvidenceResponse,
)
from app.overview.service import (
    calculate_stats,
    category_counts,
    choose_effective_scope,
    ensure_summary_cache,
    load_summary_inputs,
    lock_project_for_summary,
    requirements_in_scope,
    source_fingerprint,
    validate_highlights,
)
from app.overview.tasks import run_summary
from app.overview.types import RequestedSummaryScope, SummaryHighlight
from app.projects.service import get_owned_project


router = APIRouter(prefix="/api/projects/{project_id}", tags=["overview"])


@router.get("/analysis-overview", response_model=AnalysisOverviewResponse)
def get_analysis_overview(
    project_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
    scope: RequestedSummaryScope = Query(default="auto"),
) -> AnalysisOverviewResponse:
    get_owned_project(db, project_id, user.id)
    # Serialize cache creation per project so concurrent first reads cannot race
    # against the (project_id, scope) unique constraint.
    lock_project_for_summary(db, project_id)
    requirements, records_by_id = load_summary_inputs(db, project_id)
    if not requirements:
        return AnalysisOverviewResponse(
            empty=True,
            effective_scope="all",
            summary_state=SummaryState.PENDING,
            stale=False,
            stats=calculate_stats([]),
            category_counts=category_counts([]),
            highlights=[],
            fallback_requirements=[],
            updated_at=None,
        )
    effective_scope = choose_effective_scope(scope, requirements)
    scoped = requirements_in_scope(requirements, effective_scope)
    fingerprint = source_fingerprint(scoped)
    summary, should_schedule, stale = ensure_summary_cache(
        db, project_id, effective_scope, fingerprint
    )
    if should_schedule:
        db.commit()
        try:
            run_summary.delay(str(project_id), effective_scope, fingerprint)
        except Exception as error:  # noqa: BLE001 - retain stats and allow retry
            summary.state = SummaryState.FAILED
            summary.error_code = "summary_queue_failed"
            summary.error_message = str(error)[:1000]
            db.commit()
    else:
        db.flush()

    parsed_highlights: list[SummaryHighlight] = []
    for raw in summary.highlights:
        try:
            parsed_highlights.append(SummaryHighlight.model_validate(raw))
        except ValidationError:
            continue
    highlights = validate_highlights(parsed_highlights, scoped)
    use_fallback = summary.state == SummaryState.FAILED or (
        summary.state == SummaryState.SUCCEEDED and not highlights
    )
    fallback = []
    if use_fallback:
        for item in scoped:
            record = records_by_id[item.id]
            fallback.append(
                FallbackRequirementResponse(
                    id=item.id,
                    text=item.text,
                    category=item.category,
                    mandatory=item.mandatory,
                    review_state=item.review_state,
                    evidence=[
                        OverviewEvidenceResponse(
                            quote=evidence.quote,
                            verified=evidence.verified,
                            locator=evidence.document_block.locator,
                        )
                        for evidence in record.evidence
                    ],
                )
            )
    return AnalysisOverviewResponse(
        effective_scope=effective_scope,
        summary_state=summary.state,
        stale=stale,
        stats=calculate_stats(requirements),
        category_counts=category_counts(scoped),
        highlights=highlights,
        fallback_requirements=fallback,
        updated_at=summary.completed_at or summary.updated_at,
    )
