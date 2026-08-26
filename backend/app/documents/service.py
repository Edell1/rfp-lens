from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Document, DocumentState, Project
from app.documents.storage import FileTooLargeError, LocalFileStore, build_storage_key
from app.documents.validation import DocumentValidationError, detect_document_format
from app.projects.service import get_owned_project


MEDIA_TYPES = {
    "pdf": "application/pdf",
    "hwpx": "application/hwp+zip",
}


def _validation_detail(code: str, message: str | None = None) -> dict[str, str]:
    return {"code": code, "message": message or code}


def get_owned_document(
    db: Session, project_id: UUID, document_id: UUID, owner_id: UUID
) -> Document:
    get_owned_project(db, project_id, owner_id)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.project_id == project_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def list_owned_documents(
    db: Session, project_id: UUID, owner_id: UUID
) -> list[Document]:
    get_owned_project(db, project_id, owner_id)
    return list(
        db.scalars(
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
        )
    )


def save_uploaded_document(
    db: Session,
    project: Project,
    owner_id: UUID,
    upload: UploadFile,
    settings: Settings,
) -> Document:
    document_id = uuid4()
    storage_key = build_storage_key(owner_id, project.id, document_id)
    store = LocalFileStore(settings.storage_root)

    try:
        stored = store.save(upload.file, storage_key, settings.max_upload_bytes)
    except FileTooLargeError as error:
        raise HTTPException(
            status_code=413,
            detail=_validation_detail("file_too_large"),
        ) from error

    try:
        document_format = detect_document_format(stored.path)
    except DocumentValidationError as error:
        store.delete(storage_key)
        raise HTTPException(
            status_code=422,
            detail=_validation_detail(error.code, error.message),
        ) from error

    original_name = Path(upload.filename or "document").name
    if len(original_name) > 255:
        store.delete(storage_key)
        raise HTTPException(
            status_code=422,
            detail=_validation_detail("filename_too_long"),
        )

    document = Document(
        id=document_id,
        project_id=project.id,
        original_name=original_name,
        media_type=MEDIA_TYPES[document_format],
        checksum_sha256=stored.checksum_sha256,
        storage_key=storage_key,
        state=DocumentState.UPLOADED,
    )
    db.add(document)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        store.delete(storage_key)
        raise
    db.refresh(document)
    return document


def delete_owned_document(
    db: Session, document: Document, settings: Settings
) -> None:
    storage_key = document.storage_key
    db.delete(document)
    db.commit()
    LocalFileStore(settings.storage_root).delete(storage_key)
