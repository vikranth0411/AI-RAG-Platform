from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.nl_sql import (
    DatabaseSchema,
    NLQueryRequest,
    NLQueryResponse,
    SQLExecuteRequest,
    SQLGenerateRequest,
    SQLGenerateResponse,
    SQLResult,
    SQLValidateRequest,
    SQLValidateResponse,
)
from app.services.nl_sql_service import NLSQLService

router = APIRouter()


def get_nl_sql_service(db: AsyncSession = Depends(get_db)) -> NLSQLService:
    """Provide a natural-language SQL service for the request database session."""
    return NLSQLService(db)


@router.get("/schema", response_model=DatabaseSchema, status_code=status.HTTP_200_OK)
async def read_database_schema(
    _: User = Depends(get_current_user),
    nl_sql_service: NLSQLService = Depends(get_nl_sql_service),
) -> DatabaseSchema:
    """Extract database schema metadata for NL-to-SQL generation."""
    return await nl_sql_service.extract_schema()


@router.post("/generate", response_model=SQLGenerateResponse, status_code=status.HTTP_200_OK)
async def generate_sql(
    payload: SQLGenerateRequest,
    _: User = Depends(get_current_user),
    nl_sql_service: NLSQLService = Depends(get_nl_sql_service),
) -> SQLGenerateResponse:
    """Generate a read-only SQL statement from natural language."""
    sql = await nl_sql_service.generate_sql(
        question=payload.question,
        max_rows=payload.max_rows,
    )
    return SQLGenerateResponse(question=payload.question, sql=sql)


@router.post("/validate", response_model=SQLValidateResponse, status_code=status.HTTP_200_OK)
async def validate_sql(
    payload: SQLValidateRequest,
    _: User = Depends(get_current_user),
    nl_sql_service: NLSQLService = Depends(get_nl_sql_service),
) -> SQLValidateResponse:
    """Validate SQL before execution."""
    return nl_sql_service.validate_sql(payload.sql)


@router.post("/execute", response_model=SQLResult, status_code=status.HTTP_200_OK)
async def execute_sql(
    payload: SQLExecuteRequest,
    _: User = Depends(get_current_user),
    nl_sql_service: NLSQLService = Depends(get_nl_sql_service),
) -> SQLResult:
    """Safely execute validated read-only SQL and return formatted results."""
    return await nl_sql_service.execute_sql(sql=payload.sql, max_rows=payload.max_rows)


@router.post("/query", response_model=NLQueryResponse, status_code=status.HTTP_200_OK)
async def query_with_natural_language(
    payload: NLQueryRequest,
    _: User = Depends(get_current_user),
    nl_sql_service: NLSQLService = Depends(get_nl_sql_service),
) -> NLQueryResponse:
    """Generate, validate, execute, and format SQL from a natural-language question."""
    return await nl_sql_service.query(question=payload.question, max_rows=payload.max_rows)


@router.get("/status", status_code=status.HTTP_200_OK)
async def nl_sql_status() -> dict[str, str]:
    """Return natural-language SQL module implementation status."""
    return {"module": "nl_sql", "status": "implemented"}
