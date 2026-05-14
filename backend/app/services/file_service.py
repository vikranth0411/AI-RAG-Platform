import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile, status

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.uploaded_file import UploadedFile
from app.models.user import User
from app.repositories.file_repository import FileRepository

ALLOWED_EXTENSIONS = {"csv", "pdf", "txt", "json", "py", "js", "java", "cpp"}
ALLOWED_CONTENT_TYPES = {
    "application/json",
    "application/pdf",
    "application/vnd.ms-excel",
    "application/octet-stream",
    "application/javascript",
    "application/x-javascript",
    "application/x-python-code",
    "application/x-python",
    "text/csv",
    "text/ecmascript",
    "text/javascript",
    "text/plain",
    "text/x-c",
    "text/x-c++src",
    "text/x-java-source",
    "text/x-python",
}
CHUNK_SIZE_BYTES = 1024 * 1024
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class FileService:
    """Business service for validating and storing uploaded files."""

    def __init__(self, file_repository: FileRepository) -> None:
        self.file_repository = file_repository

    @property
    def max_upload_size_bytes(self) -> int:
        """Return the configured upload limit in bytes."""
        return settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    async def upload_file(self, *, file: UploadFile, current_user: User) -> UploadedFile:
        """Validate, store, and persist metadata for an uploaded file."""
        original_filename = Path(file.filename or "").name
        extension = self._validate_file_type(original_filename, file.content_type)
        safe_original_filename = self._safe_original_filename(original_filename)
        stored_filename = f"{uuid4().hex}.{extension}"
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        storage_path = upload_dir / stored_filename

        size_bytes = await self._write_limited_file(file, storage_path)

        try:
            return await self.file_repository.create(
                owner_id=current_user.id,
                original_filename=safe_original_filename,
                stored_filename=stored_filename,
                content_type=file.content_type or "application/octet-stream",
                file_extension=extension,
                size_bytes=size_bytes,
                storage_path=str(storage_path),
            )
        except Exception:
            storage_path.unlink(missing_ok=True)
            raise

    async def list_files(self, *, current_user: User) -> list[UploadedFile]:
        """Return uploaded file metadata for the current user."""
        return await self.file_repository.list_by_owner(current_user.id)

    def _validate_file_type(self, filename: str, content_type: str | None) -> str:
        """Validate extension and MIME type for an uploaded file."""
        extension = Path(filename).suffix.lower().lstrip(".")
        if not extension or extension not in ALLOWED_EXTENSIONS:
            raise AppError(
                "Unsupported file type",
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                code="unsupported_file_type",
            )

        if content_type and content_type.lower() not in ALLOWED_CONTENT_TYPES:
            raise AppError(
                "Unsupported content type",
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                code="unsupported_content_type",
            )
        return extension

    async def _write_limited_file(self, file: UploadFile, storage_path: Path) -> int:
        """Stream an upload to disk while enforcing the configured size limit."""
        size_bytes = 0
        try:
            with storage_path.open("wb") as destination:
                while chunk := await file.read(CHUNK_SIZE_BYTES):
                    size_bytes += len(chunk)
                    if size_bytes > self.max_upload_size_bytes:
                        raise AppError(
                            f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB upload limit",
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            code="file_too_large",
                        )
                    destination.write(chunk)
        except Exception:
            storage_path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

        if size_bytes == 0:
            storage_path.unlink(missing_ok=True)
            raise AppError(
                "Uploaded file is empty",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="empty_file",
            )
        return size_bytes

    def _safe_original_filename(self, filename: str) -> str:
        """Return a sanitized display filename for metadata storage."""
        cleaned = SAFE_FILENAME_PATTERN.sub("_", filename).strip("._")
        if not cleaned:
            raise AppError(
                "Invalid filename",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="invalid_filename",
            )
        return cleaned[:255]
