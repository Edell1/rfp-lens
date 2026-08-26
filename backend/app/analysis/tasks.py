from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.analysis.prompt import PROMPT_VERSION
from app.analysis.service import AnalysisService, create_requirement_provider
from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.db import session_factory
from app.db.models import (
    AnalysisJob,
    Document,
    DocumentBlockRecord,
    DocumentState,
    Evidence,
    JobState,
    Requirement,
)
from app.parsing.types import DocumentBlock, SourceLocator


task_settings = get_settings()
task_session_factory = session_factory


def _provider_model_name() -> str:
    if task_settings.ai_provider == "fake":
        return "synthetic-fixture-v1"
    return task_settings.openai_model


@celery_app.task(name="analysis.run_analysis", acks_late=True)
def run_analysis(document_id: str) -> str:
    parsed_id = UUID(document_id)
    with task_session_factory() as db:
        document = db.scalar(
            select(Document).where(Document.id == parsed_id).with_for_update()
        )
        if document is None:
            return "not_found"

        job = AnalysisJob(
            project_id=document.project_id,
            document_id=document.id,
            state=JobState.RUNNING,
            provider=task_settings.ai_provider,
            model=_provider_model_name(),
            prompt_version=PROMPT_VERSION,
            started_at=datetime.now(UTC),
        )
        db.add(job)
        db.flush()

        records = list(
            db.scalars(
                select(DocumentBlockRecord)
                .where(DocumentBlockRecord.document_id == document.id)
                .order_by(DocumentBlockRecord.order)
            )
        )
        blocks = [
            DocumentBlock(
                block_id=record.block_id,
                order=record.order,
                kind=record.kind,
                text=record.text,
                heading_path=record.heading_path,
                locator=SourceLocator.model_validate(record.locator),
                metadata=record.block_metadata,
            )
            for record in records
        ]

        try:
            provider = create_requirement_provider(task_settings)
            outcome = AnalysisService(provider).analyze(blocks)
        except Exception as error:
            job.state = JobState.FAILED
            job.error_code = "analysis_failed"
            job.error_message = str(error)[:1000]
            job.completed_at = datetime.now(UTC)
            document.state = DocumentState.FAILED
            document.error_code = "analysis_failed"
            document.error_message = "Requirement extraction could not be completed"
            db.commit()
            return document.state.value

        records_by_block_id = {record.block_id: record for record in records}
        for extracted in outcome.requirements:
            valid_evidence = [
                evidence
                for evidence in extracted.evidence
                if evidence.source_block_id in records_by_block_id
            ]
            if not valid_evidence:
                continue
            requirement = Requirement(
                project_id=document.project_id,
                document_id=document.id,
                analysis_job_id=job.id,
                text=extracted.requirement,
                category=extracted.category,
                mandatory=extracted.mandatory,
                confidence=extracted.confidence,
                review_state=extracted.review_state,
            )
            db.add(requirement)
            db.flush()
            for evidence in valid_evidence:
                db.add(
                    Evidence(
                        requirement_id=requirement.id,
                        document_block_id=records_by_block_id[
                            evidence.source_block_id
                        ].id,
                        quote=evidence.quote,
                        verified=evidence.verified,
                    )
                )

        job.provider = outcome.usage.provider
        job.model = outcome.usage.model
        job.prompt_version = outcome.usage.prompt_version
        job.latency_ms = outcome.usage.latency_ms
        job.input_tokens = outcome.usage.input_tokens
        job.output_tokens = outcome.usage.output_tokens
        job.provider_usage = {
            "total_chunks": outcome.total_chunks,
            "failed_chunks": outcome.failed_chunks,
        }
        job.completed_at = datetime.now(UTC)

        if outcome.total_chunks == 0 or outcome.failed_chunks == outcome.total_chunks:
            job.state = JobState.FAILED
            document.state = DocumentState.FAILED
            document.error_code = "analysis_failed"
            document.error_message = "All requirement extraction chunks failed"
        elif outcome.failed_chunks:
            job.state = JobState.PARTIAL
            document.state = DocumentState.PARTIAL
            document.error_code = "analysis_partial"
            document.error_message = "Some requirement extraction chunks failed"
        else:
            job.state = JobState.SUCCEEDED
            document.state = DocumentState.REVIEW_REQUIRED
            document.error_code = None
            document.error_message = None

        db.commit()
        return document.state.value
