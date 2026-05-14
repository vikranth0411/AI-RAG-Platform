from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.uploaded_file import UploadedFile


class FileRepository:
    """Database access layer for uploaded file metadata."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        owner_id: UUID,
        original_filename: str,
        stored_filename: str,
        content_type: str,
        file_extension: str,
        size_bytes: int,
        storage_path: str,
    ) -> UploadedFile:
        """Persist and return uploaded file metadata."""
        uploaded_file = UploadedFile(
            owner_id=owner_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=content_type,
            file_extension=file_extension,
            size_bytes=size_bytes,
            storage_path=storage_path,
        )
        self.db.add(uploaded_file)
        await self.db.commit()
        await self.db.refresh(uploaded_file)
        return uploaded_file

    async def list_by_owner(self, owner_id: UUID) -> list[UploadedFile]:
        """Return uploaded files owned by a user, newest first."""
        result = await self.db.execute(
            select(UploadedFile)
            .where(UploadedFile.owner_id == owner_id)
            .order_by(UploadedFile.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_owned_file(self, *, file_id: UUID, owner_id: UUID) -> UploadedFile | None:
        """Return a single uploaded file owned by a user."""
        result = await self.db.execute(
            select(UploadedFile).where(
                UploadedFile.id == file_id,
                UploadedFile.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()
