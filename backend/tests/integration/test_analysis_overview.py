from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AnalysisJob,
    AnalysisSummary,
    Document,
    DocumentBlockRecord,
    DocumentState,
    Evidence,
    JobState,
    Project,
    Requirement,
    RequirementCategory,
    ReviewState,
    SummaryState,
    User,
)
from app.overview.tasks import run_summary


def register(client: TestClient, email: str) -> dict[str, str]:
    password = "Correct-Horse-2026"
    client.post("/api/auth/register", json={"email": email, "password": password})
    token = client.post(
        "/api/auth/token", data={"username": email, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def seed_overview(db: Session, owner_email: str) -> tuple[Project, list[Requirement]]:
    owner = db.scalar(select(User).where(User.email == owner_email))
    assert owner is not None
    project = Project(owner=owner, name="최종 분석 결과")
    document = Document(
        project=project,
        original_name="rfp.hwpx",
        media_type="application/hwp+zip",
        checksum_sha256="c" * 64,
        storage_key=f"fixture/{uuid4()}",
        state=DocumentState.REVIEW_REQUIRED,
    )
    block = DocumentBlockRecord(
        document=document,
        block_id="section-0-p-1",
        order=0,
        kind="paragraph",
        text="중소기업만 신청 가능. 정부출연금은 5억원 이내이다.",
        heading_path=[],
        locator={"format": "hwpx", "section": "section0.xml", "paragraph": 1},
        block_metadata={},
    )
    job = AnalysisJob(
        project=project,
        document=document,
        state=JobState.SUCCEEDED,
        provider="fake",
        model="fixture",
        prompt_version="requirements-v1",
    )
    requirements = [
        Requirement(
            project=project,
            document=document,
            analysis_job=job,
            text="중소기업만 신청 가능",
            category=RequirementCategory.ELIGIBILITY,
            mandatory=True,
            confidence="high",
            review_state=ReviewState.CONFIRMED,
        ),
        Requirement(
            project=project,
            document=document,
            analysis_job=job,
            text="정부출연금은 5억원 이내",
            category=RequirementCategory.BUDGET,
            mandatory=True,
            confidence="high",
            review_state=ReviewState.PENDING,
        ),
        Requirement(
            project=project,
            document=document,
            analysis_job=job,
            text="제외된 참고 항목",
            category=RequirementCategory.OTHER,
            mandatory=False,
            confidence="low",
            review_state=ReviewState.REJECTED,
        ),
    ]
    for index, requirement in enumerate(requirements):
        db.add(
            Evidence(
                requirement=requirement,
                document_block=block,
                quote=requirement.text,
                verified=index != 1,
            )
        )
    db.commit()
    return project, requirements


def test_overview_is_owner_scoped_and_schedules_missing_cache_once(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    owner = register(client, "overview-owner@example.com")
    outsider = register(client, "overview-outsider@example.com")
    project, requirements = seed_overview(db_session, "overview-owner@example.com")
    queued: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "app.overview.router.run_summary.delay",
        lambda *args: queued.append(args),
    )

    response = client.get(
        f"/api/projects/{project.id}/analysis-overview", headers=owner
    )
    repeated = client.get(
        f"/api/projects/{project.id}/analysis-overview", headers=owner
    )

    assert response.status_code == repeated.status_code == 200
    body = response.json()
    assert body["effective_scope"] == "reviewed"
    assert body["summary_state"] == "pending"
    assert body["stats"] == {
        "total": 3,
        "confirmed_or_edited": 1,
        "pending": 1,
        "rejected": 1,
        "unverified_evidence": 1,
    }
    assert body["category_counts"]["eligibility"] == 1
    assert len(queued) == 1
    assert queued[0][0:2] == (str(project.id), "reviewed")
    assert client.get(
        f"/api/projects/{project.id}/analysis-overview", headers=outsider
    ).status_code == 404
    assert str(requirements[0].id) not in response.text or body["highlights"] == []


def test_stale_success_is_kept_while_refresh_is_queued(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    headers = register(client, "stale-summary@example.com")
    project, requirements = seed_overview(db_session, "stale-summary@example.com")
    monkeypatch.setattr("app.overview.router.run_summary.delay", lambda *args: None)
    client.get(f"/api/projects/{project.id}/analysis-overview", headers=headers)
    summary = db_session.scalar(select(AnalysisSummary))
    assert summary is not None
    summary.state = SummaryState.SUCCEEDED
    summary.highlights = [
        {
            "category": "eligibility",
            "headline": "중소기업 지원 자격",
            "detail": "신청 가능 기업 유형 확인",
            "requirement_ids": [str(requirements[0].id)],
        }
    ]
    summary.completed_at = datetime.now(UTC)
    db_session.commit()
    requirements[0].review_state = ReviewState.EDITED
    requirements[0].updated_at = datetime.now(UTC) + timedelta(seconds=1)
    db_session.commit()

    body = client.get(
        f"/api/projects/{project.id}/analysis-overview", headers=headers
    ).json()

    assert body["summary_state"] == "pending"
    assert body["stale"] is True
    assert body["highlights"][0]["headline"] == "중소기업 지원 자격"


def test_failed_summary_returns_deterministic_requirement_fallback(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    headers = register(client, "failed-summary@example.com")
    project, requirements = seed_overview(db_session, "failed-summary@example.com")
    monkeypatch.setattr("app.overview.router.run_summary.delay", lambda *args: None)
    client.get(
        f"/api/projects/{project.id}/analysis-overview",
        headers=headers,
        params={"scope": "all"},
    )
    summary = db_session.scalar(
        select(AnalysisSummary).where(AnalysisSummary.project_id == project.id)
    )
    assert summary is not None
    summary.state = SummaryState.FAILED
    summary.error_code = "summary_failed"
    summary.error_message = "provider unavailable"
    db_session.commit()

    body = client.get(
        f"/api/projects/{project.id}/analysis-overview",
        headers=headers,
        params={"scope": "all"},
    ).json()

    assert body["summary_state"] == "failed"
    assert {item["id"] for item in body["fallback_requirements"]} == {
        str(requirements[0].id),
        str(requirements[1].id),
    }


def test_queue_failure_keeps_overview_available_and_retries_on_next_read(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    headers = register(client, "queue-summary@example.com")
    project, _ = seed_overview(db_session, "queue-summary@example.com")
    attempts = 0

    def dispatch(*args):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("redis unavailable")

    monkeypatch.setattr("app.overview.router.run_summary.delay", dispatch)

    failed = client.get(
        f"/api/projects/{project.id}/analysis-overview",
        headers=headers,
        params={"scope": "all"},
    )
    retried = client.get(
        f"/api/projects/{project.id}/analysis-overview",
        headers=headers,
        params={"scope": "all"},
    )

    assert failed.status_code == 200
    assert failed.json()["summary_state"] == "failed"
    assert len(failed.json()["fallback_requirements"]) == 2
    assert retried.status_code == 200
    assert retried.json()["summary_state"] == "pending"
    assert attempts == 2


def test_failed_stale_regeneration_preserves_last_successful_highlights(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    headers = register(client, "preserve-summary@example.com")
    project, requirements = seed_overview(db_session, "preserve-summary@example.com")
    monkeypatch.setattr("app.overview.router.run_summary.delay", lambda *args: None)
    client.get(
        f"/api/projects/{project.id}/analysis-overview",
        headers=headers,
        params={"scope": "all"},
    )
    summary = db_session.scalar(
        select(AnalysisSummary).where(AnalysisSummary.project_id == project.id)
    )
    assert summary is not None
    previous = {
        "category": "eligibility",
        "headline": "이전 지원 자격 요약",
        "detail": "재생성 실패 중에도 유지",
        "requirement_ids": [str(requirements[0].id)],
    }
    summary.highlights = [previous]
    summary.highlights_fingerprint = "0" * 64
    summary.state = SummaryState.PENDING
    db_session.commit()

    class FailingProvider:
        def summarize(self, requirements):
            raise TimeoutError("summary timeout")

    factory = sessionmaker(
        bind=db_session.connection(), autoflush=False, expire_on_commit=False
    )
    monkeypatch.setattr("app.overview.tasks.task_session_factory", factory)
    monkeypatch.setattr(
        "app.overview.tasks.create_summary_provider", lambda settings: FailingProvider()
    )

    assert run_summary.run(
        str(project.id), "all", summary.source_fingerprint
    ) == "failed"
    db_session.expire_all()
    refreshed = db_session.get(AnalysisSummary, summary.id)
    assert refreshed is not None
    assert refreshed.state == SummaryState.FAILED
    assert refreshed.highlights == [previous]
    response = client.get(
        f"/api/projects/{project.id}/analysis-overview",
        headers=headers,
        params={"scope": "all"},
    )
    assert response.json()["stale"] is True
    assert response.json()["highlights"][0]["headline"] == previous["headline"]


def test_empty_project_returns_dedicated_state_without_scheduling(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    headers = register(client, "empty-summary@example.com")
    owner = db_session.scalar(
        select(User).where(User.email == "empty-summary@example.com")
    )
    assert owner is not None
    project = Project(owner=owner, name="분석 전 프로젝트")
    db_session.add(project)
    db_session.commit()
    queued = []
    monkeypatch.setattr(
        "app.overview.router.run_summary.delay", lambda *args: queued.append(args)
    )

    response = client.get(
        f"/api/projects/{project.id}/analysis-overview", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["empty"] is True
    assert response.json()["stats"]["total"] == 0
    assert queued == []
    assert db_session.scalar(
        select(AnalysisSummary).where(AnalysisSummary.project_id == project.id)
    ) is None
