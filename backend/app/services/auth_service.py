from fastapi import status

from app.core.exceptions import AppError
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token, UserCreate, UserLogin


class AuthService:
    """Business service for registration, login, and token issuance."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def register_user(self, payload: UserCreate) -> User:
        """Register a new active user with a hashed password."""
        existing_user = await self.user_repository.get_by_email(payload.email)
        if existing_user:
            raise AppError(
                "User with this email already exists",
                status_code=status.HTTP_409_CONFLICT,
                code="user_already_exists",
            )

        return await self.user_repository.create(
            email=payload.email,
            hashed_password=get_password_hash(payload.password),
            full_name=payload.full_name,
            role=UserRole.USER.value,
        )

    async def authenticate_user(self, payload: UserLogin) -> User:
        """Authenticate a user by email and password."""
        user = await self.user_repository.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise AppError(
                "Invalid email or password",
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="invalid_credentials",
            )
        if not user.is_active:
            raise AppError(
                "User account is inactive",
                status_code=status.HTTP_403_FORBIDDEN,
                code="inactive_user",
            )
        return user

    async def login(self, payload: UserLogin) -> Token:
        """Authenticate and issue a JWT access token."""
        user = await self.authenticate_user(payload)
        access_token = create_access_token(
            subject=str(user.id),
            claims={"role": user.role or UserRole.USER.value},
        )
        return Token(access_token=access_token)
