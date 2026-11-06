from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus, unquote, urlsplit

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    """Raised when deployment settings are missing or unsafe."""


INSECURE_VALUES = {
    "change-me",
    "changeme",
    "password",
    "secret",
    "placeholder",
    "replace-me",
    "your-secret",
    "your-secret-key",
    "your-password",
}
INSECURE_MARKERS = (
    "change-me",
    "changeme",
    "placeholder",
    "replace-me",
    "your-secret",
    "your-password",
)


def _contains_insecure_marker(value: str) -> bool:
    """Return whether a value contains an obvious documented placeholder."""
    normalized = value.casefold()
    return normalized in INSECURE_VALUES or any(
        marker in normalized for marker in INSECURE_MARKERS
    )


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    ALGORITHM: str = "HS256"
    APP_ENV: Literal["development", "testing", "staging", "production"] = "development"
    APP_NAME: str = "AI RAG Platform"
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"

    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "rag_platform"
    POSTGRES_USER: str = "rag_user"
    POSTGRES_PASSWORD: str = "rag_password"
    DATABASE_URL: str | None = None

    SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "rag_documents"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-70b-versatile"
    GROQ_TEMPERATURE: float = 0.2
    GROQ_MAX_TOKENS: int = 1024
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 150
    RAG_DEFAULT_TOP_K: int = 5
    NL_SQL_MAX_ROWS: int = 100

    UPLOAD_DIR: str = "/app/data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 25

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @property
    def cors_origins(self) -> list[str]:
        """Return configured CORS origins as a normalized list."""
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Return an async SQLAlchemy PostgreSQL URL."""
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
                return self.DATABASE_URL
            if self.DATABASE_URL.startswith("postgresql+psycopg2://"):
                return self.DATABASE_URL.replace(
                    "postgresql+psycopg2://",
                    "postgresql+asyncpg://",
                    1,
                )
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            if self.DATABASE_URL.startswith("postgres://"):
                return self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL

        username = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return (
            f"postgresql+asyncpg://{username}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    def validate_production_configuration(self) -> None:
        """Reject insecure or implicit credentials when running in production."""
        if self.APP_ENV != "production":
            return

        if "SECRET_KEY" not in self.model_fields_set:
            raise ConfigurationError(
                "Production requires SECRET_KEY to be explicitly configured. "
                "Set it to a unique random value of at least 32 characters."
            )
        secret_key = self.SECRET_KEY.strip()
        if (
            len(secret_key) < 32
            or _contains_insecure_marker(secret_key)
            or not secret_key
        ):
            raise ConfigurationError(
                "Production SECRET_KEY is insecure. Set a unique random value "
                "of at least 32 characters."
            )

        database_url = self.DATABASE_URL
        if database_url and "DATABASE_URL" in self.model_fields_set:
            self._validate_production_database_url(database_url)
            return

        required_database_fields = (
            "POSTGRES_HOST",
            "POSTGRES_PORT",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
        )
        missing = [
            field
            for field in required_database_fields
            if field not in self.model_fields_set
        ]
        if missing:
            names = ", ".join(missing)
            raise ConfigurationError(
                "Production requires explicit database settings: "
                f"{names}. Configure these values or provide DATABASE_URL."
            )

        if not self.POSTGRES_HOST.strip() or not self.POSTGRES_DB.strip():
            raise ConfigurationError(
                "Production database host and database name must not be empty."
            )
        if not 1 <= self.POSTGRES_PORT <= 65535:
            raise ConfigurationError("Production POSTGRES_PORT must be between 1 and 65535.")
        self._validate_database_credentials(self.POSTGRES_USER, self.POSTGRES_PASSWORD)

    def _validate_production_database_url(self, database_url: str) -> None:
        """Validate required PostgreSQL URL components without echoing its value."""
        try:
            parsed = urlsplit(database_url)
            port = parsed.port
            valid_url = (
                parsed.scheme
                in {
                    "postgres",
                    "postgresql",
                    "postgresql+asyncpg",
                    "postgresql+psycopg2",
                }
                and bool(parsed.hostname)
                and bool(parsed.path.strip("/"))
                and bool(parsed.username)
                and bool(parsed.password)
                and (port is None or 1 <= port <= 65535)
            )
        except ValueError:
            valid_url = False
            parsed = None

        if not valid_url or parsed is None:
            raise ConfigurationError(
                "Production DATABASE_URL must include a PostgreSQL host, database, "
                "username, and password."
            )
        self._validate_database_credentials(
            unquote(parsed.username or ""),
            unquote(parsed.password or ""),
        )

    def _validate_database_credentials(self, username: str, password: str) -> None:
        """Reject known example credentials and weak production passwords."""
        if _contains_insecure_marker(username.strip()) or username.strip().casefold() in {
            "rag_user",
            "postgres",
        }:
            raise ConfigurationError(
                "Production database username is a documented or insecure default. "
                "Configure a dedicated application database user."
            )
        normalized_password = password.strip().casefold()
        if (
            len(password.strip()) < 16
            or _contains_insecure_marker(password.strip())
            or normalized_password == "rag_password"
        ):
            raise ConfigurationError(
                "Production database password is insecure. Configure a unique "
                "password of at least 16 characters."
            )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    configured_settings = Settings()
    configured_settings.validate_production_configuration()
    return configured_settings


settings = get_settings()
