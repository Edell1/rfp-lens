from uuid import UUID

from fastapi import APIRouter, Response

from app.auth.dependencies import CurrentUser, DatabaseSession
from app.compliance.export import build_compliance_workbook
from app.compliance.schemas import (
    CompliancePatch,
    ComplianceResponse,
    EvidenceResponse,
    RequirementPatch,
    RequirementResponse,
)
from app.compliance.service import (
    export_rows,
    format_locator,
    get_compliance_item,
    get_requirement,
    list_compliance_items,
    list_requirements,
    update_compliance_item,
    update_requirement,
)
from app.db.models import (
    ComplianceItem,
    Requirement,
    RequirementCategory,
    ReviewState,
)


router = APIRouter(prefix="/api/projects/{project_id}", tags=["compliance"])


def _requirement_response(requirement: Requirement) -> RequirementResponse:
    return RequirementResponse(
        id=requirement.id,
        project_id=requirement.project_id,
        document_id=requirement.document_id,
        text=requirement.text,
        category=requirement.category,
        mandatory=requirement.mandatory,
        confidence=requirement.confidence,
        review_state=requirement.review_state,
        evidence=[
            EvidenceResponse(
                id=evidence.id,
                block_id=evidence.document_block.block_id,
                quote=evidence.quote,
                verified=evidence.verified,
                locator=evidence.document_block.locator,
            )
            for evidence in requirement.evidence
        ],
        created_at=requirement.created_at,
        updated_at=requirement.updated_at,
    )


def _compliance_response(item: ComplianceItem) -> ComplianceResponse:
    evidence = item.requirement.evidence
    return ComplianceResponse(
        id=item.id,
        requirement_id=item.requirement_id,
        requirement_text=item.requirement.text,
        category=item.requirement.category,
        mandatory=item.requirement.mandatory,
        evidence_quote="\n".join(entry.quote for entry in evidence),
        source_location="\n".join(
            format_locator(entry.document_block.locator) for entry in evidence
        ),
        importance=item.importance,
        proposal_section=item.proposal_section,
        owner_note=item.owner_note,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/requirements", response_model=list[RequirementResponse])
def get_requirements(
    project_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
    category: RequirementCategory | None = None,
    review_state: ReviewState | None = None,
) -> list[RequirementResponse]:
    return [
        _requirement_response(requirement)
        for requirement in list_requirements(
            db,
            project_id,
            user.id,
            category=category,
            review_state=review_state,
        )
    ]


@router.patch(
    "/requirements/{requirement_id}", response_model=RequirementResponse
)
def patch_requirement(
    project_id: UUID,
    requirement_id: UUID,
    payload: RequirementPatch,
    db: DatabaseSession,
    user: CurrentUser,
) -> RequirementResponse:
    requirement = get_requirement(
        db, project_id, requirement_id, user.id, for_update=True
    )
    return _requirement_response(
        update_requirement(db, requirement, payload, user.id)
    )


@router.get("/compliance", response_model=list[ComplianceResponse])
def get_compliance(
    project_id: UUID, db: DatabaseSession, user: CurrentUser
) -> list[ComplianceResponse]:
    return [
        _compliance_response(item)
        for item in list_compliance_items(db, project_id, user.id)
    ]


@router.patch("/compliance/{item_id}", response_model=ComplianceResponse)
def patch_compliance(
    project_id: UUID,
    item_id: UUID,
    payload: CompliancePatch,
    db: DatabaseSession,
    user: CurrentUser,
) -> ComplianceResponse:
    item = get_compliance_item(db, project_id, item_id, user.id, for_update=True)
    return _compliance_response(
        update_compliance_item(db, item, payload, user.id)
    )


@router.get("/compliance.xlsx")
def export_compliance(
    project_id: UUID, db: DatabaseSession, user: CurrentUser
) -> Response:
    items = list_compliance_items(db, project_id, user.id)
    content = build_compliance_workbook(export_rows(items))
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="compliance.xlsx"'},
    )
