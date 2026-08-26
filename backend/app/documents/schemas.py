from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models import DocumentState


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    original_name: str
    media_type: str
    checksum_sha256: str
    state: DocumentState
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
