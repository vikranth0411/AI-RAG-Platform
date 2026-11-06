from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class shared by the SQLAlchemy models and Alembic metadata."""
