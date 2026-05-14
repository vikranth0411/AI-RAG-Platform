import re

from fastapi import status
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.nl_sql import (
    ColumnInfo,
    DatabaseSchema,
    ForeignKeyInfo,
    NLQueryResponse,
    SQLResult,
    SQLValidateResponse,
    TableInfo,
)

SQL_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You generate PostgreSQL SELECT queries for a read-only analytics endpoint. "
            "Use only the provided schema. Return SQL only, with no markdown, prose, comments, "
            "or trailing explanation. Never generate INSERT, UPDATE, DELETE, DDL, COPY, CALL, "
            "transaction commands, or multiple statements. Keep results bounded with LIMIT {max_rows}.",
        ),
        (
            "human",
            "Schema:\n{schema}\n\nQuestion:\n{question}\n\nSQL:",
        ),
    ]
)

MUTATING_OR_UNSAFE_PATTERN = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|truncate|create|replace|merge|grant|revoke|"
    r"copy|call|execute|do|vacuum|analyze|refresh|lock|set|reset|commit|rollback|"
    r"begin|start|prepare|deallocate|listen|notify|unlisten|"
    r"pg_sleep|pg_read_file|pg_read_binary_file|lo_import|lo_export|dblink|"
    r"nextval|setval|pg_advisory_lock|pg_advisory_xact_lock"
    r")\b",
    re.IGNORECASE,
)
COMMENT_PATTERN = re.compile(r"(--|/\*)")
LOCKING_CLAUSE_PATTERN = re.compile(
    r"\bfor\s+(update|no\s+key\s+update|share|key\s+share)\b",
    re.IGNORECASE,
)


class NLSQLService:
    """Natural-language to SQL service with schema extraction and secure execution."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def extract_schema(self) -> DatabaseSchema:
        """Extract table, column, primary key, and foreign key metadata."""

        def inspect_schema(connection) -> DatabaseSchema:
            inspector = inspect(connection)
            tables: list[TableInfo] = []
            for table_name in sorted(inspector.get_table_names(schema="public")):
                if table_name == "alembic_version":
                    continue

                pk_columns = set(
                    inspector.get_pk_constraint(table_name, schema="public").get(
                        "constrained_columns",
                        [],
                    )
                )
                columns = [
                    ColumnInfo(
                        name=column["name"],
                        type=str(column["type"]),
                        nullable=bool(column.get("nullable", True)),
                        primary_key=column["name"] in pk_columns,
                    )
                    for column in inspector.get_columns(table_name, schema="public")
                ]
                foreign_keys = [
                    ForeignKeyInfo(
                        constrained_columns=list(fk.get("constrained_columns") or []),
                        referred_table=str(fk.get("referred_table")),
                        referred_columns=list(fk.get("referred_columns") or []),
                    )
                    for fk in inspector.get_foreign_keys(table_name, schema="public")
                ]
                tables.append(
                    TableInfo(
                        name=table_name,
                        columns=columns,
                        foreign_keys=foreign_keys,
                    )
                )
            return DatabaseSchema(tables=tables)

        connection = await self.db.connection()
        return await connection.run_sync(inspect_schema)

    async def generate_sql(self, *, question: str, max_rows: int) -> str:
        """Generate a PostgreSQL SELECT statement from a natural-language question."""
        if not settings.GROQ_API_KEY:
            raise AppError(
                "GROQ_API_KEY is not configured",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="llm_not_configured",
            )

        schema = await self.extract_schema()
        chain = SQL_PROMPT | ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            temperature=0,
            max_tokens=settings.GROQ_MAX_TOKENS,
        ) | StrOutputParser()

        try:
            generated_sql = await chain.ainvoke(
                {
                    "schema": self._format_schema_for_prompt(schema),
                    "question": question,
                    "max_rows": max_rows,
                }
            )
        except Exception as exc:
            raise AppError(
                "SQL generation failed",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="sql_generation_error",
            ) from exc

        sql = self._clean_generated_sql(generated_sql)
        validation = self.validate_sql(sql)
        if not validation.valid:
            raise AppError(
                "Generated SQL failed validation",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="invalid_generated_sql",
            )
        return self._ensure_limit(sql, max_rows)

    def validate_sql(self, sql: str) -> SQLValidateResponse:
        """Validate SQL as a single read-only PostgreSQL SELECT statement."""
        cleaned_sql = self._normalize_sql(sql)
        errors: list[str] = []

        if not cleaned_sql:
            errors.append("SQL is empty")
        if COMMENT_PATTERN.search(cleaned_sql):
            errors.append("SQL comments are not allowed")
        if self._contains_multiple_statements(cleaned_sql):
            errors.append("Multiple SQL statements are not allowed")
        if not self._is_select_statement(cleaned_sql):
            errors.append("Only SELECT statements are allowed")
        if MUTATING_OR_UNSAFE_PATTERN.search(cleaned_sql):
            errors.append("Unsafe SQL keyword or function detected")
        if LOCKING_CLAUSE_PATTERN.search(cleaned_sql):
            errors.append("Locking SELECT clauses are not allowed")

        return SQLValidateResponse(valid=not errors, sql=cleaned_sql, errors=errors)

    async def execute_sql(self, *, sql: str, max_rows: int) -> SQLResult:
        """Validate and execute read-only SQL with bounded formatted results."""
        validation = self.validate_sql(sql)
        if not validation.valid:
            raise AppError(
                "; ".join(validation.errors),
                status_code=status.HTTP_400_BAD_REQUEST,
                code="invalid_sql",
            )

        bounded_sql = self._ensure_limit(validation.sql, max_rows)
        wrapped_sql = f"SELECT * FROM ({bounded_sql}) AS nl_sql_result LIMIT :max_rows_plus_one"

        try:
            result = await self.db.execute(text(wrapped_sql), {"max_rows_plus_one": max_rows + 1})
            mappings = result.mappings().all()
        except Exception as exc:
            raise AppError(
                "SQL execution failed",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="sql_execution_error",
            ) from exc
        finally:
            await self.db.rollback()

        rows = [dict(row) for row in mappings[:max_rows]]
        columns = list(rows[0].keys()) if rows else list(result.keys())
        return SQLResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=len(mappings) > max_rows,
        )

    async def query(self, *, question: str, max_rows: int) -> NLQueryResponse:
        """Generate, validate, execute, and format a natural-language SQL query."""
        sql = await self.generate_sql(question=question, max_rows=max_rows)
        result = await self.execute_sql(sql=sql, max_rows=max_rows)
        return NLQueryResponse(question=question, sql=sql, result=result)

    def _format_schema_for_prompt(self, schema: DatabaseSchema) -> str:
        """Render schema metadata compactly for SQL generation prompts."""
        lines: list[str] = []
        for table in schema.tables:
            lines.append(f"Table: {table.name}")
            for column in table.columns:
                markers = []
                if column.primary_key:
                    markers.append("primary key")
                if not column.nullable:
                    markers.append("not null")
                marker_text = f" ({', '.join(markers)})" if markers else ""
                lines.append(f"- {column.name}: {column.type}{marker_text}")
            for fk in table.foreign_keys:
                lines.append(
                    "- foreign key: "
                    f"{', '.join(fk.constrained_columns)} -> "
                    f"{fk.referred_table}({', '.join(fk.referred_columns)})"
                )
        return "\n".join(lines)

    def _clean_generated_sql(self, sql: str) -> str:
        """Remove common LLM formatting wrappers from generated SQL."""
        cleaned = sql.strip()
        cleaned = re.sub(r"^```(?:sql)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        return self._normalize_sql(cleaned)

    def _normalize_sql(self, sql: str) -> str:
        """Normalize SQL whitespace and remove a single trailing semicolon."""
        cleaned = sql.strip()
        if cleaned.endswith(";"):
            cleaned = cleaned[:-1].strip()
        return re.sub(r"\s+", " ", cleaned)

    def _contains_multiple_statements(self, sql: str) -> bool:
        """Return whether SQL contains statement separators beyond a trailing semicolon."""
        stripped = sql.strip()
        if stripped.endswith(";"):
            stripped = stripped[:-1]
        return ";" in stripped

    def _is_select_statement(self, sql: str) -> bool:
        """Return whether SQL starts with SELECT or WITH."""
        return bool(re.match(r"^\s*(select|with)\b", sql, flags=re.IGNORECASE))

    def _ensure_limit(self, sql: str, max_rows: int) -> str:
        """Append a LIMIT when the SQL does not already include one."""
        cleaned = self._normalize_sql(sql)
        if re.search(r"\blimit\s+\d+\b", cleaned, flags=re.IGNORECASE):
            return cleaned
        return f"{cleaned} LIMIT {max_rows}"
