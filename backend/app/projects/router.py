from uuid import UUID

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.auth.dependencies import CurrentUser, DatabaseSession
from app.core.config import Settings, get_settings
from app.documents.storage import LocalFileStore
from app.projects.schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from app.projects.service import (
    create_project,
    delete_project,
    get_owned_project,
    list_owned_projects,
    update_project,
)


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
def list_projects(db: DatabaseSession, user: CurrentUser) -> list[ProjectResponse]:
    return [
        ProjectResponse.model_validate(project)
        for project in list_owned_projects(db, user.id)
    ]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create(
    payload: ProjectCreate, db: DatabaseSession, user: CurrentUser
) -> ProjectResponse:
    return ProjectResponse.model_validate(create_project(db, user.id, payload.name))


@router.get("/{project_id}", response_model=ProjectResponse)
def get(project_id: UUID, db: DatabaseSession, user: CurrentUser) -> ProjectResponse:
    return ProjectResponse.model_validate(get_owned_project(db, project_id, user.id))


@router.patch("/{project_id}", response_model=ProjectResponse)
def update(
    project_id: UUID,
    payload: ProjectUpdate,
    db: DatabaseSession,
    user: CurrentUser,
) -> ProjectResponse:
    project = get_owned_project(db, project_id, user.id)
    return ProjectResponse.model_validate(update_project(db, project, payload.name))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    project_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    project = get_owned_project(db, project_id, user.id)
    storage_keys = delete_project(db, project)
    store = LocalFileStore(settings.storage_root)
    for storage_key in storage_keys:
        store.delete(storage_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
