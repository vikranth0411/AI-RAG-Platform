from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings


class ColumnInfo(BaseModel):
    """Database column metadata exposed to NL-to-SQL prompts."""

    name: str
    type: str
    nullable: bool
    primary_key: bool = False


class ForeignKeyInfo(BaseModel):
    """Foreign key relationship metadata."""

    constrained_columns: list[str]
    referred_table: str
    referred_columns: list[str]


class TableInfo(BaseModel):
    """Database table metadata."""

    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo]


class DatabaseSchema(BaseModel):
    """Extracted database schema."""

    tables: list[TableInfo]


class SQLGenerateRequest(BaseModel):
    """Natural-language SQL generation request."""

    question: str = Field(..., min_length=1)
    max_rows: int = Field(default=settings.NL_SQL_MAX_ROWS, ge=1, le=500)


class SQLGenerateResponse(BaseModel):
    """Generated SQL response."""

    question: str
    sql: str


class SQLValidateRequest(BaseModel):
    """SQL validation request."""

    sql: str = Field(..., min_length=1)


class SQLValidateResponse(BaseModel):
    """SQL validation result."""

    valid: bool
    sql: str
    errors: list[str] = Field(default_factory=list)


class SQLExecuteRequest(BaseModel):
    """Secure SQL execution request."""

    sql: str = Field(..., min_length=1)
    max_rows: int = Field(default=settings.NL_SQL_MAX_ROWS, ge=1, le=500)


class SQLResult(BaseModel):
    """Formatted SQL result set."""

    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool


class NLQueryRequest(BaseModel):
    """Natural-language query request that generates and executes SQL."""

    question: str = Field(..., min_length=1)
    max_rows: int = Field(default=settings.NL_SQL_MAX_ROWS, ge=1, le=500)


class NLQueryResponse(BaseModel):
    """Natural-language query response with generated SQL and results."""

    question: str
    sql: str
    result: SQLResult
