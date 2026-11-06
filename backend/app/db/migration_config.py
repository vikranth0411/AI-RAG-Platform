from collections.abc import Mapping
import os

from sqlalchemy.engine import make_url


def get_migration_database_url(
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return the dedicated async database URL used only by Alembic."""
    environment = os.environ if environ is None else environ
    database_url = environment.get("MIGRATION_DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "MIGRATION_DATABASE_URL must be set to run database migrations."
        )

    try:
        parsed_url = make_url(database_url)
    except Exception:
        raise RuntimeError(
            "MIGRATION_DATABASE_URL must be a valid PostgreSQL async URL."
        ) from None

    if parsed_url.drivername != "postgresql+asyncpg":
        raise RuntimeError(
            "MIGRATION_DATABASE_URL must use the postgresql+asyncpg driver."
        )
    return database_url
