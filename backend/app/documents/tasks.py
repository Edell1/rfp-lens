from pathlib import Path
from uuid import UUID

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import delete, select

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.db import session_factory
from app.db.models import Document, DocumentBlockRecord, DocumentState
from app.documents.storage import LocalFileStore
from app.parsing.hwpx import HwpxParseError
from app.parsing.pdf import PdfParseError
from app.parsing.registry import UnsupportedParserError, create_default_registry


task_settings = get_settings()
task_session_factory = session_factory


def _format_name(media_type: str) -> str:
    formats = {
        "application/pdf": "pdf",
        "application/hwp+zip": "hwpx",
    }
    try:
        return formats[media_type]
    except KeyError as error:
        raise UnsupportedParserError(media_type) from error


@celery_app.task(
    bind=True,
    name="documents.process_document",
    max_retries=3,
    acks_late=True,
)
def process_document(self, document_id: str) -> str:
    parsed_id = UUID(document_id)
    with task_session_factory() as db:
        document = db.scalar(
            select(Document).where(Document.id == parsed_id).with_for_update()
        )
        if document is None:
            return "not_found"

        document.state = DocumentState.PARSING
        document.error_code = None
        document.error_message = None
        db.commit()

        try:
            store = LocalFileStore(task_settings.storage_root)
            with store.open(document.storage_key) as source:
                parser = create_default_registry().get(_format_name(document.media_type))
                result = parser.parse(Path(source.name))
        except OSError as error:
            try:
                raise self.retry(countdown=min(2 ** (self.request.retries + 1), 30))
            except MaxRetriesExceededError:
                document.state = DocumentState.FAILED
                document.error_code = "storage_unavailable"
                document.error_message = "Stored document could not be opened"
                db.commit()
                return document.state.value
        except (PdfParseError, HwpxParseError, UnsupportedParserError) as error:
            document.state = DocumentState.FAILED
            document.error_code = getattr(error, "code", "unsupported_parser")
            document.error_message = str(error)[:1000]
            db.commit()
            return document.state.value

        db.execute(
            delete(DocumentBlockRecord).where(
                DocumentBlockRecord.document_id == document.id
            )
        )
        if result.requires_ocr:
            document.state = DocumentState.OCR_REQUIRED
            document.error_code = "ocr_required"
            document.error_message = result.warnings[0].message if result.warnings else None
            db.commit()
            return document.state.value

        for block in result.blocks:
            db.add(
                DocumentBlockRecord(
                    document_id=document.id,
                    block_id=block.block_id,
                    order=block.order,
                    kind=block.kind,
                    text=block.text,
                    heading_path=block.heading_path,
                    locator=block.locator.model_dump(mode="json", exclude_none=True),
                    block_metadata=block.metadata,
                )
            )
        document.state = DocumentState.ANALYZING
        db.commit()
        return document.state.value
