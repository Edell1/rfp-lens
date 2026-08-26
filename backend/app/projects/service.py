from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, Project


def get_owned_project(
    db: Session, project_id: UUID, owner_id: UUID
) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == owner_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def list_owned_projects(db: Session, owner_id: UUID) -> list[Project]:
    return list(
        db.scalars(
            select(Project)
            .where(Project.owner_id == owner_id)
            .order_by(Project.created_at.desc())
        )
    )


def create_project(db: Session, owner_id: UUID, name: str) -> Project:
    project = Project(owner_id=owner_id, name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: Project, name: str) -> Project:
    project.name = name
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> list[str]:
    storage_keys = list(
        db.scalars(
            select(Document.storage_key).where(Document.project_id == project.id)
        )
    )
    db.delete(project)
    db.commit()
    return storage_keys
