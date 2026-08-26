from io import BytesIO
from uuid import UUID
from zipfile import ZIP_STORED, ZipFile

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document
from app.documents.storage import LocalFileStore


PASSWORD = "Correct-Horse-2026"


def register_and_login(client: TestClient, email: str) -> dict[str, str]:
    assert client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD}
    ).status_code == 201
    token = client.post(
        "/api/auth/token", data={"username": email, "password": PASSWORD}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_hwpx_bytes() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("mimetype", "application/hwp+zip", compress_type=ZIP_STORED)
        archive.writestr("Contents/content.hpf", "<package />")
    return output.getvalue()


def create_project(client: TestClient, headers: dict[str, str], name: str = "RFP") -> str:
    response = client.post("/api/projects", headers=headers, json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_pdf_upload_uses_safe_storage_key_and_can_be_deleted(
    client: TestClient, db_session: Session
) -> None:
    headers = register_and_login(client, "pdf-owner@example.com")
    project_id = create_project(client, headers)

    response = client.post(
        f"/api/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("../../proposal.pdf", b"%PDF-1.7\nbody", "application/pdf")},
    )

    assert response.status_code == 201
    document_id = response.json()["id"]
    document = db_session.scalar(
        select(Document).where(Document.id == UUID(document_id))
    )
    assert document is not None
    assert "proposal.pdf" not in document.storage_key
    store = LocalFileStore(client.app.state.settings.storage_root)
    with store.open(document.storage_key) as stored:
        assert stored.read().startswith(b"%PDF-")

    deleted = client.delete(
        f"/api/projects/{project_id}/documents/{document_id}", headers=headers
    )
    assert deleted.status_code == 204
    try:
        store.open(document.storage_key)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("stored file was not deleted")


def test_hwpx_upload_is_listed(client: TestClient) -> None:
    headers = register_and_login(client, "hwpx-owner@example.com")
    project_id = create_project(client, headers)

    uploaded = client.post(
        f"/api/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("notice.hwpx", make_hwpx_bytes(), "application/octet-stream")},
    )
    listed = client.get(f"/api/projects/{project_id}/documents", headers=headers)

    assert uploaded.status_code == 201
    assert uploaded.json()["media_type"] == "application/hwp+zip"
    assert [item["id"] for item in listed.json()] == [uploaded.json()["id"]]


def test_invalid_upload_returns_typed_error(client: TestClient) -> None:
    headers = register_and_login(client, "invalid-owner@example.com")
    project_id = create_project(client, headers)

    response = client.post(
        f"/api/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("notice.txt", b"not a document", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_format"


def test_cross_user_document_operations_return_not_found(client: TestClient) -> None:
    alice = register_and_login(client, "upload-alice@example.com")
    project_id = create_project(client, alice)
    uploaded = client.post(
        f"/api/projects/{project_id}/documents",
        headers=alice,
        files={"file": ("rfp.pdf", b"%PDF-1.7\n", "application/pdf")},
    ).json()
    bob = register_and_login(client, "upload-bob@example.com")

    assert client.get(
        f"/api/projects/{project_id}/documents", headers=bob
    ).status_code == 404
    assert client.delete(
        f"/api/projects/{project_id}/documents/{uploaded['id']}", headers=bob
    ).status_code == 404


def test_deleting_project_removes_stored_documents(
    client: TestClient, db_session: Session
) -> None:
    headers = register_and_login(client, "project-delete@example.com")
    project_id = create_project(client, headers)
    uploaded = client.post(
        f"/api/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("rfp.pdf", b"%PDF-1.7\n", "application/pdf")},
    ).json()
    document = db_session.get(Document, UUID(uploaded["id"]))
    assert document is not None
    storage_key = document.storage_key

    assert client.delete(f"/api/projects/{project_id}", headers=headers).status_code == 204

    store = LocalFileStore(client.app.state.settings.storage_root)
    try:
        store.open(storage_key)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("project deletion left a stored document")
