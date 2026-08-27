from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.celery_app import celery_app
from app.core.config import Settings
from app.db.models import (
    AnalysisJob,
    AnalysisSummary,
    Document,
    DocumentState,
    Evidence,
    JobState,
    Project,
    Requirement,
    SummaryState,
    User,
)
from app.documents.storage import LocalFileStore, build_storage_key
from app.documents.tasks import process_document
from tests.fixtures.hwpx_factory import build_hwpx


@pytest.fixture
def analysis_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        jwt_secret="test-secret-that-is-long-enough-for-hs256",
        storage_root=tmp_path / "analysis-storage",
        ai_provider="fake",
    )


@pytest.fixture(autouse=True)
def configure_eager_workflow(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    analysis_settings: Settings,
) -> Generator[None, None, None]:
    import app.analysis.tasks as analysis_tasks
    import app.documents.tasks as document_tasks
    import app.overview.tasks as overview_tasks

    factory = sessionmaker(
        bind=db_session.connection(), autoflush=False, expire_on_commit=False
    )
    monkeypatch.setattr(document_tasks, "task_session_factory", factory)
    monkeypatch.setattr(document_tasks, "task_settings", analysis_settings)
    monkeypatch.setattr(analysis_tasks, "task_session_factory", factory)
    monkeypatch.setattr(analysis_tasks, "task_settings", analysis_settings)
    monkeypatch.setattr(overview_tasks, "task_session_factory", factory)
    monkeypatch.setattr(overview_tasks, "task_settings", analysis_settings)

    previous_eager = celery_app.conf.task_always_eager
    previous_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = previous_eager
    celery_app.conf.task_eager_propagates = previous_propagates


def test_parsing_enqueues_analysis_and_persists_verified_requirement(
    db_session: Session,
    analysis_settings: Settings,
    tmp_path: Path,
) -> None:
    user = User(email=f"analysis-{uuid4()}@example.com", password_hash="hash")
    project = Project(owner=user, name="Analysis project")
    db_session.add(project)
    db_session.flush()
    document_id = uuid4()
    key = build_storage_key(user.id, project.id, document_id)
    source = build_hwpx(tmp_path / "analysis.hwpx")
    with source.open("rb") as stream:
        stored = LocalFileStore(analysis_settings.storage_root).save(
            stream, key, max_bytes=26_214_400
        )
    document = Document(
        id=document_id,
        project=project,
        original_name="analysis.hwpx",
        media_type="application/hwp+zip",
        checksum_sha256=stored.checksum_sha256,
        storage_key=key,
        state=DocumentState.UPLOADED,
    )
    db_session.add(document)
    db_session.commit()

    parsing_result = process_document.run(str(document.id))
    db_session.expire_all()

    refreshed = db_session.get(Document, document.id)
    job = db_session.scalar(
        select(AnalysisJob).where(AnalysisJob.document_id == document.id)
    )
    requirement = db_session.scalar(
        select(Requirement).where(Requirement.document_id == document.id)
    )
    evidence = db_session.scalar(
        select(Evidence).where(Evidence.requirement_id == requirement.id)
        if requirement is not None
        else select(Evidence).where(False)
    )
    summary = db_session.scalar(
        select(AnalysisSummary).where(AnalysisSummary.project_id == project.id)
    )

    assert parsing_result == DocumentState.ANALYZING.value
    assert refreshed is not None and refreshed.state == DocumentState.REVIEW_REQUIRED
    assert job is not None and job.state == JobState.SUCCEEDED
    assert job.provider == "fake"
    assert requirement is not None
    assert requirement.text == "중소기업만 신청 가능"
    assert evidence is not None and evidence.verified is True
    assert evidence.quote == "중소기업만 신청 가능"
    assert summary is not None and summary.state == SummaryState.SUCCEEDED
    assert summary.provider == "fake"
    assert summary.highlights[0]["requirement_ids"] == [str(requirement.id)]
