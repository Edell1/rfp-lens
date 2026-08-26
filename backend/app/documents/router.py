from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.auth.dependencies import CurrentUser, DatabaseSession
from app.core.config import Settings, get_settings
from app.documents.schemas import DocumentResponse
from app.documents.service import (
    delete_owned_document,
    get_owned_document,
    list_owned_documents,
    save_uploaded_document,
)
from app.projects.service import get_owned_project


router = APIRouter(prefix="/api/projects/{project_id}/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    project_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    project = get_owned_project(db, project_id, user.id)
    document = save_uploaded_document(db, project, user.id, file, settings)
    return DocumentResponse.model_validate(document)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    project_id: UUID, db: DatabaseSession, user: CurrentUser
) -> list[DocumentResponse]:
    return [
        DocumentResponse.model_validate(document)
        for document in list_owned_documents(db, project_id, user.id)
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    project_id: UUID,
    document_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> DocumentResponse:
    document = get_owned_document(db, project_id, document_id, user.id)
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    project_id: UUID,
    document_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    document = get_owned_document(db, project_id, document_id, user.id)
    delete_owned_document(db, document, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
