from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.db import session_factory
from app.db.models import AnalysisSummary, SummaryScope, SummaryState
from app.overview.provider import create_summary_provider
from app.overview.service import (
    load_summary_inputs,
    requirements_in_scope,
    source_fingerprint,
    validate_highlights,
)
from app.settings.service import resolve_runtime_settings


task_settings = get_settings()
task_session_factory = session_factory


@celery_app.task(name="overview.generate_summary", acks_late=True)
def run_summary(project_id: str, scope: str, expected_fingerprint: str) -> str:
    parsed_project_id = UUID(project_id)
    parsed_scope = SummaryScope(scope)
    with task_session_factory() as db:
        summary = db.scalar(
            select(AnalysisSummary)
            .where(
                AnalysisSummary.project_id == parsed_project_id,
                AnalysisSummary.scope == parsed_scope,
            )
            .with_for_update()
        )
        if summary is None or summary.source_fingerprint != expected_fingerprint:
            return "obsolete"
        if summary.state == SummaryState.SUCCEEDED:
            return summary.state.value
        summary.state = SummaryState.RUNNING
        summary.started_at = datetime.now(UTC)
        summary.error_code = None
        summary.error_message = None
        db.commit()

        try:
            requirements, _ = load_summary_inputs(db, parsed_project_id)
            scoped = requirements_in_scope(requirements, scope)
            if source_fingerprint(scoped) != expected_fingerprint:
                return "obsolete"
            settings = resolve_runtime_settings(db, task_settings)
            batch, usage = create_summary_provider(settings).summarize(scoped)
            highlights = validate_highlights(batch.highlights, scoped)
            if not highlights:
                raise ValueError("No valid summary highlights")
            summary = db.scalar(
                select(AnalysisSummary)
                .where(AnalysisSummary.id == summary.id)
                .with_for_update()
            )
            if summary is None or summary.source_fingerprint != expected_fingerprint:
                return "obsolete"
            summary.state = SummaryState.SUCCEEDED
            summary.provider = usage.provider
            summary.model = usage.model
            summary.prompt_version = usage.prompt_version
            summary.highlights = [item.model_dump(mode="json") for item in highlights]
            summary.highlights_fingerprint = expected_fingerprint
            summary.completed_at = datetime.now(UTC)
            db.commit()
            return summary.state.value
        except Exception as error:  # noqa: BLE001 - persisted for UI fallback
            summary = db.scalar(
                select(AnalysisSummary)
                .where(AnalysisSummary.id == summary.id)
                .with_for_update()
            )
            if summary is None or summary.source_fingerprint != expected_fingerprint:
                return "obsolete"
            summary.state = SummaryState.FAILED
            summary.error_code = "summary_failed"
            summary.error_message = str(error)[:1000]
            summary.completed_at = datetime.now(UTC)
            db.commit()
            return summary.state.value
