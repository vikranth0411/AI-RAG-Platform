from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends, Security, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session to API routes."""
    async for session in get_db_session():
        yield session


async def get_current_user(
    token: str = Security(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a bearer access token."""
    try:
        payload = TokenPayload(**decode_access_token(token))
        user_id = UUID(payload.sub)
    except (ValueError, TypeError):
        raise AppError(
            "Invalid authentication credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_token",
        ) from None

    user = await UserRepository(db).get_by_id(user_id)
    if not user:
        raise AppError(
            "Invalid authentication credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_token",
        )
    if not user.is_active:
        raise AppError(
            "User account is inactive",
            status_code=status.HTTP_403_FORBIDDEN,
            code="inactive_user",
        )
    return user


def require_roles(*allowed_roles: UserRole):
    """Build a dependency that restricts access to the provided roles."""

    async def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in {role.value for role in allowed_roles}:
            raise AppError(
                "Insufficient permissions",
                status_code=status.HTTP_403_FORBIDDEN,
                code="insufficient_permissions",
            )
        return current_user

    return role_dependency
