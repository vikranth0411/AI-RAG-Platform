import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.db.migration_config import get_migration_database_url
import app.models  # noqa: F401  Register all mapped models with Base.metadata.

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Render migrations without opening a database connection."""
    context.configure(
        url=get_migration_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations using an active synchronous SQLAlchemy connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Open the dedicated migration connection and run Alembic revisions."""
    connectable = create_async_engine(
        get_migration_database_url(),
        poolclass=pool.NullPool,
        echo=False,
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    except Exception as exc:
        error_type = type(exc).__name__
        raise RuntimeError(
            "Database migration failed "
            f"({error_type}). Verify MIGRATION_DATABASE_URL and migration privileges."
        ) from None
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations with an async PostgreSQL connection."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
