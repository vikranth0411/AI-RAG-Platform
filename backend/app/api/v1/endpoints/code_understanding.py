from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.code_understanding import (
    CodeAnalysisRequest,
    CodeAnalysisResponse,
    CodeBugsResponse,
    CodeComplexityResponse,
    CodeExplainResponse,
    CodeOptimizationResponse,
)
from app.services.code_understanding_service import CodeUnderstandingService

router = APIRouter()


def get_code_understanding_service() -> CodeUnderstandingService:
    """Provide a code understanding service."""
    return CodeUnderstandingService()


@router.post("/analyze", response_model=CodeAnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_code(
    payload: CodeAnalysisRequest,
    _: User = Depends(get_current_user),
    service: CodeUnderstandingService = Depends(get_code_understanding_service),
) -> CodeAnalysisResponse:
    """Explain code, detect bugs, suggest optimizations, and analyze complexity."""
    return await service.analyze(payload)


@router.post("/explain", response_model=CodeExplainResponse, status_code=status.HTTP_200_OK)
async def explain_code(
    payload: CodeAnalysisRequest,
    _: User = Depends(get_current_user),
    service: CodeUnderstandingService = Depends(get_code_understanding_service),
) -> CodeExplainResponse:
    """Explain what submitted code does."""
    return await service.explain(payload)


@router.post("/bugs", response_model=CodeBugsResponse, status_code=status.HTTP_200_OK)
async def detect_bugs(
    payload: CodeAnalysisRequest,
    _: User = Depends(get_current_user),
    service: CodeUnderstandingService = Depends(get_code_understanding_service),
) -> CodeBugsResponse:
    """Detect likely defects and risky code behavior."""
    return await service.detect_bugs(payload)


@router.post(
    "/optimizations",
    response_model=CodeOptimizationResponse,
    status_code=status.HTTP_200_OK,
)
async def suggest_optimizations(
    payload: CodeAnalysisRequest,
    _: User = Depends(get_current_user),
    service: CodeUnderstandingService = Depends(get_code_understanding_service),
) -> CodeOptimizationResponse:
    """Suggest practical optimizations for submitted code."""
    return await service.suggest_optimizations(payload)


@router.post(
    "/complexity",
    response_model=CodeComplexityResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_complexity(
    payload: CodeAnalysisRequest,
    _: User = Depends(get_current_user),
    service: CodeUnderstandingService = Depends(get_code_understanding_service),
) -> CodeComplexityResponse:
    """Analyze code complexity and return static metrics."""
    return await service.analyze_complexity(payload)


@router.get("/status", status_code=status.HTTP_200_OK)
async def code_understanding_status() -> dict[str, str]:
    """Return code understanding module implementation status."""
    return {"module": "code_understanding", "status": "implemented"}
