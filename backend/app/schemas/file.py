from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UploadedFileRead(BaseModel):
    """Public metadata for an uploaded file."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    original_filename: str
    stored_filename: str
    content_type: str
    file_extension: str
    size_bytes: int
    created_at: datetime


class UploadPolicy(BaseModel):
    """File upload constraints exposed to clients."""

    allowed_extensions: list[str]
    max_size_mb: int
