from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.compliance.export import ExportRow
from app.compliance.schemas import CompliancePatch, RequirementPatch
from app.db.models import (
    ComplianceItem,
    Evidence,
    Requirement,
    RequirementCategory,
    ReviewState,
)
from app.projects.service import get_owned_project


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": code, "message": message})


def _require_fresh(actual: datetime, expected: datetime) -> None:
    if actual != expected:
        raise _conflict("stale_update", "The record changed after it was loaded")


def _requirement_options():
    return selectinload(Requirement.evidence).selectinload(Evidence.document_block)


def list_requirements(
    db: Session,
    project_id: UUID,
    owner_id: UUID,
    *,
    category: RequirementCategory | None = None,
    review_state: ReviewState | None = None,
) -> list[Requirement]:
    get_owned_project(db, project_id, owner_id)
    statement = (
        select(Requirement)
        .where(Requirement.project_id == project_id)
        .options(_requirement_options())
        .order_by(Requirement.created_at.desc(), Requirement.id)
    )
    if category is not None:
        statement = statement.where(Requirement.category == category)
    if review_state is not None:
        statement = statement.where(Requirement.review_state == review_state)
    return list(db.scalars(statement))


def get_requirement(
    db: Session,
    project_id: UUID,
    requirement_id: UUID,
    owner_id: UUID,
    *,
    for_update: bool = False,
) -> Requirement:
    get_owned_project(db, project_id, owner_id)
    statement = (
        select(Requirement)
        .where(
            Requirement.id == requirement_id,
            Requirement.project_id == project_id,
        )
        .options(_requirement_options())
    )
    if for_update:
        statement = statement.with_for_update()
    requirement = db.scalar(statement)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return requirement


def update_requirement(
    db: Session,
    requirement: Requirement,
    payload: RequirementPatch,
    owner_id: UUID,
) -> Requirement:
    _require_fresh(requirement.updated_at, payload.updated_at)
    text_changed = payload.text is not None and payload.text != requirement.text
    next_state = ReviewState.EDITED if text_changed else payload.review_state
    if next_state in {ReviewState.CONFIRMED, ReviewState.EDITED}:
        has_unverified = any(not evidence.verified for evidence in requirement.evidence)
        if has_unverified and not payload.confirm_unverified:
            raise _conflict(
                "unverified_evidence",
                "Explicit confirmation is required for unverified evidence",
            )

    if payload.text is not None:
        requirement.text = payload.text
    if next_state is not None:
        requirement.review_state = next_state
    requirement.updated_at = datetime.now(UTC)

    if requirement.review_state in {ReviewState.CONFIRMED, ReviewState.EDITED}:
        item = db.scalar(
            select(ComplianceItem).where(
                ComplianceItem.requirement_id == requirement.id
            )
        )
        if item is None:
            db.add(
                ComplianceItem(
                    project_id=requirement.project_id,
                    requirement_id=requirement.id,
                )
            )
    elif requirement.review_state == ReviewState.REJECTED:
        db.execute(
            delete(ComplianceItem).where(
                ComplianceItem.requirement_id == requirement.id
            )
        )

    db.commit()
    db.refresh(requirement)
    return get_requirement(db, requirement.project_id, requirement.id, owner_id)


def list_compliance_items(
    db: Session, project_id: UUID, owner_id: UUID
) -> list[ComplianceItem]:
    get_owned_project(db, project_id, owner_id)
    return list(
        db.scalars(
            select(ComplianceItem)
            .join(ComplianceItem.requirement)
            .where(ComplianceItem.project_id == project_id)
            .options(
                selectinload(ComplianceItem.requirement)
                .selectinload(Requirement.evidence)
                .selectinload(Evidence.document_block)
            )
            .order_by(ComplianceItem.created_at, ComplianceItem.id)
        )
    )


def get_compliance_item(
    db: Session,
    project_id: UUID,
    item_id: UUID,
    owner_id: UUID,
    *,
    for_update: bool = False,
) -> ComplianceItem:
    get_owned_project(db, project_id, owner_id)
    statement = (
        select(ComplianceItem)
        .where(
            ComplianceItem.id == item_id,
            ComplianceItem.project_id == project_id,
        )
        .options(
            selectinload(ComplianceItem.requirement)
            .selectinload(Requirement.evidence)
            .selectinload(Evidence.document_block)
        )
    )
    if for_update:
        statement = statement.with_for_update()
    item = db.scalar(statement)
    if item is None:
        raise HTTPException(status_code=404, detail="Compliance item not found")
    return item


def update_compliance_item(
    db: Session, item: ComplianceItem, payload: CompliancePatch, owner_id: UUID
) -> ComplianceItem:
    _require_fresh(item.updated_at, payload.updated_at)
    for field in ("importance", "proposal_section", "owner_note", "status"):
        value = getattr(payload, field)
        if value is not None:
            setattr(item, field, value)
    item.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(item)
    return get_compliance_item(db, item.project_id, item.id, owner_id)


def format_locator(locator: dict[str, object]) -> str:
    parts: list[str] = []
    if locator.get("page") is not None:
        parts.append(f"{locator['page']}쪽")
    if locator.get("section") is not None:
        parts.append(str(locator["section"]))
    if locator.get("paragraph") is not None:
        parts.append(f"문단 {locator['paragraph']}")
    if locator.get("table") is not None:
        parts.append(f"표 {locator['table']}")
    return " ".join(parts) or "위치 정보 없음"


def export_rows(items: list[ComplianceItem]) -> list[ExportRow]:
    rows: list[ExportRow] = []
    for item in items:
        evidence = item.requirement.evidence
        rows.append(
            ExportRow(
                requirement=item.requirement.text,
                category=item.requirement.category.value,
                mandatory="필수" if item.requirement.mandatory else "권고",
                evidence_quote="\n".join(entry.quote for entry in evidence),
                source_location="\n".join(
                    format_locator(entry.document_block.locator) for entry in evidence
                ),
                importance=item.importance.value,
                proposal_section=item.proposal_section,
                status=item.status.value,
                owner_note=item.owner_note,
            )
        )
    return rows
