from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_roles
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token, UserCreate, UserLogin, UserRead
from app.services.auth_service import AuthService

router = APIRouter()


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Provide an auth service wired to the request database session."""
    return AuthService(UserRepository(db))


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Register a user with a hashed password."""
    return await auth_service.register_user(payload)


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login_user(
    payload: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    """Authenticate a user and return a JWT access token."""
    return await auth_service.login(payload)


@router.get("/me", response_model=UserRead, status_code=status.HTTP_200_OK)
async def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user's profile."""
    return current_user


@router.get("/admin", response_model=UserRead, status_code=status.HTTP_200_OK)
async def read_admin_user(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    """Return the authenticated admin user's profile."""
    return current_user


@router.get("/status", status_code=status.HTTP_200_OK)
async def auth_status() -> dict[str, str]:
    """Return auth module implementation status."""
    return {"module": "auth", "status": "implemented"}
