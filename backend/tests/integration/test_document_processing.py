from collections.abc import Generator
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
import pytest

from app.core.config import Settings
from app.db.models import (
    Document,
    DocumentBlockRecord,
    DocumentState,
    Project,
    User,
)
from app.documents.storage import LocalFileStore, build_storage_key
from app.documents.tasks import process_document
from tests.fixtures.hwpx_factory import build_hwpx
from tests.fixtures.pdf_factory import make_pdf


@pytest.fixture
def task_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        jwt_secret="test-secret-that-is-long-enough-for-hs256",
        storage_root=tmp_path / "worker-storage",
    )


@pytest.fixture(autouse=True)
def configure_task_runtime(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    task_settings: Settings,
) -> Generator[None, None, None]:
    import app.documents.tasks as tasks

    factory = sessionmaker(
        bind=db_session.connection(), autoflush=False, expire_on_commit=False
    )
    monkeypatch.setattr(tasks, "task_session_factory", factory)
    monkeypatch.setattr(tasks, "task_settings", task_settings)
    yield


def store_document(
    db_session: Session,
    settings: Settings,
    source: Path,
    *,
    media_type: str,
    original_name: str,
) -> Document:
    user = User(email=f"worker-{uuid4()}@example.com", password_hash="hash")
    project = Project(owner=user, name="Worker project")
    db_session.add(project)
    db_session.flush()
    document_id = uuid4()
    key = build_storage_key(user.id, project.id, document_id)
    with source.open("rb") as stream:
        stored = LocalFileStore(settings.storage_root).save(
            stream, key, max_bytes=26_214_400
        )
    document = Document(
        id=document_id,
        project=project,
        original_name=original_name,
        media_type=media_type,
        checksum_sha256=stored.checksum_sha256,
        storage_key=key,
        state=DocumentState.UPLOADED,
    )
    db_session.add(document)
    db_session.commit()
    return document


@pytest.fixture
def uploaded_hwpx(
    db_session: Session, task_settings: Settings, tmp_path: Path
) -> Document:
    path = build_hwpx(tmp_path / "worker.hwpx")
    return store_document(
        db_session,
        task_settings,
        path,
        media_type="application/hwp+zip",
        original_name="worker.hwpx",
    )


def test_process_hwpx_persists_blocks(
    db_session: Session, uploaded_hwpx: Document
) -> None:
    result = process_document.run(str(uploaded_hwpx.id))
    db_session.expire_all()
    document = db_session.get(Document, uploaded_hwpx.id)
    blocks = list(
        db_session.scalars(
            select(DocumentBlockRecord)
            .where(DocumentBlockRecord.document_id == uploaded_hwpx.id)
            .order_by(DocumentBlockRecord.order)
        )
    )

    assert result == DocumentState.ANALYZING.value
    assert document is not None and document.state == DocumentState.ANALYZING
    assert [block.order for block in blocks] == list(range(len(blocks)))
    assert [block.text for block in blocks] == [
        "1. 지원 자격",
        "중소기업만 신청 가능",
        "평가항목",
    ]


def test_scanned_pdf_moves_to_ocr_required(
    db_session: Session, task_settings: Settings, tmp_path: Path
) -> None:
    document = store_document(
        db_session,
        task_settings,
        make_pdf(tmp_path / "scan.pdf", [""]),
        media_type="application/pdf",
        original_name="scan.pdf",
    )

    process_document.run(str(document.id))
    db_session.expire_all()
    refreshed = db_session.get(Document, document.id)

    assert refreshed is not None
    assert refreshed.state == DocumentState.OCR_REQUIRED
    assert refreshed.error_code == "ocr_required"


def test_malformed_stored_content_moves_to_failed(
    db_session: Session, task_settings: Settings, tmp_path: Path
) -> None:
    source = tmp_path / "broken.pdf"
    source.write_bytes(b"not-a-pdf")
    document = store_document(
        db_session,
        task_settings,
        source,
        media_type="application/pdf",
        original_name="broken.pdf",
    )

    result = process_document.run(str(document.id))
    db_session.expire_all()
    refreshed = db_session.get(Document, document.id)

    assert result == DocumentState.FAILED.value
    assert refreshed is not None and refreshed.state == DocumentState.FAILED
    assert refreshed.error_code == "invalid_pdf"


def test_transient_storage_error_retries_without_duplicate_blocks(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    uploaded_hwpx: Document,
) -> None:
    import app.documents.tasks as tasks

    original_open = tasks.LocalFileStore.open
    calls = 0

    def fail_once(store: LocalFileStore, key: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("temporary storage failure")
        return original_open(store, key)

    monkeypatch.setattr(tasks.LocalFileStore, "open", fail_once)

    eager_result = process_document.apply(args=[str(uploaded_hwpx.id)])

    assert eager_result.get() == DocumentState.ANALYZING.value
    assert calls == 2
    process_document.run(str(uploaded_hwpx.id))

    blocks = list(
        db_session.scalars(
            select(DocumentBlockRecord).where(
                DocumentBlockRecord.document_id == uploaded_hwpx.id
            )
        )
    )
    assert len(blocks) == 3
    assert len({block.block_id for block in blocks}) == 3


def test_process_endpoint_enqueues_owned_uploaded_document(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.documents import router as document_router

    password = "Correct-Horse-2026"
    email = "process-owner@example.com"
    client.post("/api/auth/register", json={"email": email, "password": password})
    token = client.post(
        "/api/auth/token", data={"username": email, "password": password}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.post(
        "/api/projects", headers=headers, json={"name": "Process RFP"}
    ).json()["id"]
    uploaded = client.post(
        f"/api/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("rfp.pdf", b"%PDF-1.7\ntext", "application/pdf")},
    ).json()
    queued: list[str] = []
    monkeypatch.setattr(document_router.process_document, "delay", queued.append)

    response = client.post(
        f"/api/projects/{project_id}/documents/{uploaded['id']}/process",
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json()["state"] == "parsing"
    assert response.json()["block_count"] == 0
    assert queued == [uploaded["id"]]

    duplicate = client.post(
        f"/api/projects/{project_id}/documents/{uploaded['id']}/process",
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "document_already_processing"
