from collections.abc import Callable

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisJob,
    ComplianceItem,
    Document,
    DocumentState,
    JobState,
    Project,
    Requirement,
    RequirementCategory,
    User,
)


def test_project_delete_cascades_documents(
    db_session: Session, user_factory: Callable[[str], User]
) -> None:
    user = user_factory("owner@example.com")
    project = Project(owner_id=user.id, name="2027 공개 RFP")
    document = Document(
        project=project,
        original_name="rfp.hwpx",
        media_type="application/hwp+zip",
        checksum_sha256="a" * 64,
        storage_key="owner/project/document.hwpx",
        state=DocumentState.UPLOADED,
    )
    db_session.add(project)
    db_session.commit()
    document_id = document.id

    db_session.delete(project)
    db_session.commit()

    assert db_session.get(Document, document_id) is None


def test_user_email_is_unique(
    db_session: Session, user_factory: Callable[[str], User]
) -> None:
    user_factory("duplicate@example.com")
    db_session.commit()
    db_session.add(
        User(email="duplicate@example.com", password_hash="another-password-hash")
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_compliance_item_requirement_is_unique(
    db_session: Session, user_factory: Callable[[str], User]
) -> None:
    user = user_factory("matrix-owner@example.com")
    project = Project(owner_id=user.id, name="컴플라이언스 테스트")
    document = Document(
        project=project,
        original_name="rfp.pdf",
        media_type="application/pdf",
        checksum_sha256="b" * 64,
        storage_key="owner/project/document.pdf",
        state=DocumentState.ANALYZING,
    )
    job = AnalysisJob(
        project=project,
        document=document,
        state=JobState.SUCCEEDED,
        provider="fake",
        model="fixture-v1",
        prompt_version="requirements-v1",
    )
    requirement = Requirement(
        project=project,
        document=document,
        analysis_job=job,
        text="중소기업만 신청할 수 있다.",
        category=RequirementCategory.ELIGIBILITY,
        mandatory=True,
        confidence="high",
    )
    first = ComplianceItem(project=project, requirement=requirement)
    db_session.add(first)
    db_session.commit()
    db_session.add(ComplianceItem(project_id=project.id, requirement_id=requirement.id))

    with pytest.raises(IntegrityError):
        db_session.commit()
