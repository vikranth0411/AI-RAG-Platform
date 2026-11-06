import pytest

from app.core.config import ConfigurationError, get_settings


CONFIG_ENV_VARS = (
    "APP_ENV",
    "SECRET_KEY",
    "DATABASE_URL",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)


@pytest.fixture(autouse=True)
def clean_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate settings tests from local environment configuration."""
    for name in CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def configure_valid_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure explicit production secrets and database connection values."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-secure-random-production-key-123456")
    monkeypatch.setenv("POSTGRES_HOST", "db.internal.example")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "platform_prod")
    monkeypatch.setenv("POSTGRES_USER", "platform_app")
    monkeypatch.setenv("POSTGRES_PASSWORD", "long-random-db-password-abcdef")


def test_valid_production_configuration_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit production secrets and database settings are accepted."""
    configure_valid_production(monkeypatch)

    configured = get_settings()

    assert configured.APP_ENV == "production"
    assert configured.database_url.startswith("postgresql+asyncpg://")


def test_valid_production_database_url_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    """A complete explicit PostgreSQL URL is accepted as production DB config."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-secure-random-production-key-123456")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://platform_app:long-random-db-password-abcdef@"
        "db.internal.example:5432/platform_prod",
    )

    configured = get_settings()

    assert configured.database_url.startswith("postgresql+asyncpg://")


def test_production_requires_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing production signing key fails with an actionable message."""
    configure_valid_production(monkeypatch)
    monkeypatch.delenv("SECRET_KEY")

    with pytest.raises(ConfigurationError, match="SECRET_KEY.*explicitly configured"):
        get_settings()


@pytest.mark.parametrize("secret_key", ["change-me", "your-secret-key-placeholder-123456"])
def test_production_rejects_default_or_placeholder_secret(
    monkeypatch: pytest.MonkeyPatch,
    secret_key: str,
) -> None:
    """Known defaults and placeholder signing keys are rejected without echoing them."""
    configure_valid_production(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", secret_key)

    with pytest.raises(ConfigurationError) as raised:
        get_settings()

    assert "SECRET_KEY is insecure" in str(raised.value)
    assert secret_key not in str(raised.value)


def test_production_requires_explicit_database_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production cannot silently use the built-in database defaults."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-secure-random-production-key-123456")

    with pytest.raises(ConfigurationError, match="explicit database settings") as raised:
        get_settings()

    assert "POSTGRES_PASSWORD" in str(raised.value)
    assert "rag_password" not in str(raised.value)


@pytest.mark.parametrize(
    ("field", "value", "error_message"),
    [
        ("POSTGRES_USER", "rag_user", "database username is a documented"),
        ("POSTGRES_PASSWORD", "rag_password", "database password is insecure"),
    ],
)
def test_production_rejects_default_database_credentials(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
    error_message: str,
) -> None:
    """Explicitly repeating the documented local DB credentials is rejected."""
    configure_valid_production(monkeypatch)
    monkeypatch.setenv(field, value)

    with pytest.raises(ConfigurationError) as raised:
        get_settings()

    assert error_message in str(raised.value)
    assert value not in str(raised.value)


def test_development_keeps_local_defaults() -> None:
    """Development mode retains the project's convenient local defaults."""
    configured = get_settings()

    assert configured.APP_ENV == "development"
    assert configured.SECRET_KEY == "change-me"
    assert configured.POSTGRES_USER == "rag_user"
    assert configured.POSTGRES_PASSWORD == "rag_password"
