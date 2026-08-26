from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisJob,
    Document,
    DocumentBlockRecord,
    DocumentState,
    Evidence,
    JobState,
    Project,
    Requirement,
    RequirementCategory,
    ReviewState,
    User,
)


def register(client: TestClient, email: str) -> dict[str, str]:
    password = "Correct-Horse-2026"
    client.post("/api/auth/register", json={"email": email, "password": password})
    token = client.post(
        "/api/auth/token", data={"username": email, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def seed_requirement(
    db: Session, *, owner_email: str, verified: bool = True
) -> Requirement:
    user = db.scalar(select(User).where(User.email == owner_email))
    assert user is not None
    project = Project(owner=user, name="Compliance project")
    document = Document(
        project=project,
        original_name="rfp.hwpx",
        media_type="application/hwp+zip",
        checksum_sha256="a" * 64,
        storage_key=f"fixture/{uuid4()}",
        state=DocumentState.REVIEW_REQUIRED,
    )
    block = DocumentBlockRecord(
        document=document,
        block_id="section-0-p-1",
        order=0,
        kind="paragraph",
        text="중소기업만 신청 가능",
        heading_path=["지원 자격"],
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
    requirement = Requirement(
        project=project,
        document=document,
        analysis_job=job,
        text="중소기업만 신청 가능",
        category=RequirementCategory.ELIGIBILITY,
        mandatory=True,
        confidence="high",
        review_state=ReviewState.PENDING,
    )
    evidence = Evidence(
        requirement=requirement,
        document_block=block,
        quote="중소기업만 신청 가능",
        verified=verified,
    )
    db.add(evidence)
    db.commit()
    db.refresh(requirement)
    return requirement


def test_confirming_requirement_creates_compliance_item(
    client: TestClient, db_session: Session
) -> None:
    email = "review-owner@example.com"
    headers = register(client, email)
    requirement = seed_requirement(db_session, owner_email=email)

    response = client.patch(
        f"/api/projects/{requirement.project_id}/requirements/{requirement.id}",
        headers=headers,
        json={
            "review_state": "confirmed",
            "updated_at": requirement.updated_at.isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()["review_state"] == "confirmed"
    matrix = client.get(
        f"/api/projects/{requirement.project_id}/compliance", headers=headers
    )
    assert matrix.status_code == 200
    assert matrix.json()[0]["requirement_id"] == str(requirement.id)


def test_editing_requirement_sets_edited_and_rejection_removes_matrix_row(
    client: TestClient, db_session: Session
) -> None:
    email = "edit-owner@example.com"
    headers = register(client, email)
    requirement = seed_requirement(db_session, owner_email=email)
    url = f"/api/projects/{requirement.project_id}/requirements/{requirement.id}"

    edited = client.patch(
        url,
        headers=headers,
        json={
            "text": "중소기업만 신청할 수 있음",
            "updated_at": requirement.updated_at.isoformat(),
        },
    )
    assert edited.status_code == 200
    assert edited.json()["review_state"] == "edited"

    rejected = client.patch(
        url,
        headers=headers,
        json={
            "review_state": "rejected",
            "updated_at": edited.json()["updated_at"],
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["review_state"] == "rejected"
    assert client.get(
        f"/api/projects/{requirement.project_id}/compliance", headers=headers
    ).json() == []


def test_unverified_evidence_requires_explicit_confirmation(
    client: TestClient, db_session: Session
) -> None:
    email = "unverified-owner@example.com"
    headers = register(client, email)
    requirement = seed_requirement(db_session, owner_email=email, verified=False)
    url = f"/api/projects/{requirement.project_id}/requirements/{requirement.id}"
    payload = {
        "review_state": "confirmed",
        "updated_at": requirement.updated_at.isoformat(),
    }

    blocked = client.patch(url, headers=headers, json=payload)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "unverified_evidence"

    payload["confirm_unverified"] = True
    confirmed = client.patch(url, headers=headers, json=payload)
    assert confirmed.status_code == 200


def test_stale_update_and_cross_user_access_are_rejected(
    client: TestClient, db_session: Session
) -> None:
    owner = register(client, "stale-owner@example.com")
    outsider = register(client, "stale-outsider@example.com")
    requirement = seed_requirement(db_session, owner_email="stale-owner@example.com")
    url = f"/api/projects/{requirement.project_id}/requirements/{requirement.id}"
    stale_updated_at = requirement.updated_at.isoformat()

    assert client.get(
        f"/api/projects/{requirement.project_id}/requirements", headers=outsider
    ).status_code == 404
    changed = client.patch(
        url,
        headers=owner,
        json={
            "review_state": "confirmed",
            "updated_at": stale_updated_at,
        },
    )
    assert changed.status_code == 200
    stale = client.patch(
        url,
        headers=owner,
        json={
            "review_state": "rejected",
            "updated_at": stale_updated_at,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_update"


def test_requirement_filters_and_compliance_patch(
    client: TestClient, db_session: Session
) -> None:
    email = "filter-owner@example.com"
    headers = register(client, email)
    requirement = seed_requirement(db_session, owner_email=email)
    project_id = requirement.project_id

    listed = client.get(
        f"/api/projects/{project_id}/requirements",
        headers=headers,
        params={"category": "eligibility", "review_state": "pending"},
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [str(requirement.id)]

    confirmed = client.patch(
        f"/api/projects/{project_id}/requirements/{requirement.id}",
        headers=headers,
        json={
            "review_state": "confirmed",
            "updated_at": requirement.updated_at.isoformat(),
        },
    )
    item = client.get(
        f"/api/projects/{project_id}/compliance", headers=headers
    ).json()[0]
    patched = client.patch(
        f"/api/projects/{project_id}/compliance/{item['id']}",
        headers=headers,
        json={
            "updated_at": item["updated_at"],
            "importance": "high",
            "proposal_section": "2. 연구개발 필요성",
            "status": "in_progress",
            "owner_note": "근거 자료 추가",
        },
    )
    assert confirmed.status_code == 200
    assert patched.status_code == 200
    assert patched.json()["proposal_section"] == "2. 연구개발 필요성"


def test_compliance_export_is_owner_scoped(
    client: TestClient, db_session: Session
) -> None:
    owner = register(client, "export-owner@example.com")
    outsider = register(client, "export-outsider@example.com")
    requirement = seed_requirement(db_session, owner_email="export-owner@example.com")

    response = client.get(
        f"/api/projects/{requirement.project_id}/compliance.xlsx", headers=outsider
    )

    assert response.status_code == 404
