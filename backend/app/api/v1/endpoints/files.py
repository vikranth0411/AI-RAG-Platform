from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
from app.models.uploaded_file import UploadedFile
from app.models.user import User
from app.repositories.file_repository import FileRepository
from app.schemas.file import UploadPolicy, UploadedFileRead
from app.services.file_service import ALLOWED_EXTENSIONS, FileService

router = APIRouter()


def get_file_service(db: AsyncSession = Depends(get_db)) -> FileService:
    """Provide a file service wired to the request database session."""
    return FileService(FileRepository(db))


@router.post("/upload", response_model=UploadedFileRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service),
) -> UploadedFile:
    """Upload a validated file and persist its metadata."""
    return await file_service.upload_file(file=file, current_user=current_user)


@router.get("", response_model=list[UploadedFileRead], status_code=status.HTTP_200_OK)
async def list_files(
    current_user: User = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service),
) -> list[UploadedFile]:
    """List metadata for files uploaded by the authenticated user."""
    return await file_service.list_files(current_user=current_user)


@router.get("/policy", response_model=UploadPolicy, status_code=status.HTTP_200_OK)
async def upload_policy() -> UploadPolicy:
    """Return supported upload types and size limit."""
    return UploadPolicy(
        allowed_extensions=sorted(ALLOWED_EXTENSIONS),
        max_size_mb=settings.MAX_UPLOAD_SIZE_MB,
    )


@router.get("/status", status_code=status.HTTP_200_OK)
async def files_status() -> dict[str, str]:
    """Return files module implementation status."""
    return {"module": "files", "status": "implemented"}
