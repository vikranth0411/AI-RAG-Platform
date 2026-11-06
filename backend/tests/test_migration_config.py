from configparser import ConfigParser
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.base import Base
from app.db.migration_config import get_migration_database_url
import app.models  # noqa: F401  Ensure all ORM models are registered.

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def test_migration_url_uses_dedicated_environment_variable() -> None:
    """Alembic reads its own URL and does not fall back to runtime credentials."""
    migration_url = "postgresql+asyncpg://migrator:test-only@db.example.test/platform"
    environment = {
        "MIGRATION_DATABASE_URL": migration_url,
        "DATABASE_URL": "postgresql+asyncpg://runtime:test-only@db.example.test/platform",
    }

    assert get_migration_database_url(environment) == migration_url


@pytest.mark.parametrize("environment", [{}, {"DATABASE_URL": "runtime-url"}])
def test_migration_url_is_required_and_error_does_not_echo_values(
    environment: dict[str, str],
) -> None:
    """Missing migration settings fail clearly without including runtime values."""
    with pytest.raises(RuntimeError, match="MIGRATION_DATABASE_URL must be set") as raised:
        get_migration_database_url(environment)

    assert "runtime-url" not in str(raised.value)


def test_unsupported_migration_driver_error_does_not_echo_credentials() -> None:
    """Unsupported driver errors do not expose the provided URL or password."""
    secret_url = "postgresql://migrator:do-not-print@db.example.test/platform"

    with pytest.raises(RuntimeError, match="must use the postgresql") as raised:
        get_migration_database_url({"MIGRATION_DATABASE_URL": secret_url})

    assert secret_url not in str(raised.value)
    assert "do-not-print" not in str(raised.value)


def test_alembic_configuration_has_no_embedded_database_url() -> None:
    """Alembic keeps migration connection credentials outside the ini file."""
    parser = ConfigParser()
    parser.read(ALEMBIC_INI, encoding="utf-8")
    config = Config(str(ALEMBIC_INI))

    assert parser.has_section("alembic")
    assert not parser.has_option("alembic", "sqlalchemy.url")
    assert config.get_main_option("script_location") == "alembic"
    assert config.get_main_option("sqlalchemy.url") is None


def test_alembic_environment_and_revision_chain_are_available() -> None:
    """Alembic can load its environment and discover the existing revision head."""
    config = Config(str(ALEMBIC_INI))
    environment_file = BACKEND_DIR / "alembic" / "env.py"
    script_directory = ScriptDirectory.from_config(config)

    assert environment_file.is_file()
    assert script_directory.get_heads() == ["20260514_0003"]


def test_alembic_metadata_contains_all_application_models() -> None:
    """The migration metadata includes every mapped application table."""
    assert set(Base.metadata.tables) == {
        "users",
        "uploaded_files",
        "conversations",
        "messages",
    }
