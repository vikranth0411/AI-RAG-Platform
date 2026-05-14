from pydantic import BaseModel, Field


class CodeAnalysisRequest(BaseModel):
    """Request payload for AI code understanding."""

    code: str = Field(..., min_length=1, max_length=120_000)
    language: str | None = Field(default=None, max_length=50)
    filename: str | None = Field(default=None, max_length=255)


class ComplexityMetrics(BaseModel):
    """Static complexity metrics derived from the submitted code."""

    lines_of_code: int
    non_empty_lines: int
    estimated_cyclomatic_complexity: int
    functions: int
    classes: int


class CodeAnalysisResponse(BaseModel):
    """Structured code understanding response."""

    language: str
    explanation: str
    potential_bugs: list[str]
    optimization_suggestions: list[str]
    complexity_analysis: str
    metrics: ComplexityMetrics


class CodeExplainResponse(BaseModel):
    """Code explanation response."""

    language: str
    explanation: str
    metrics: ComplexityMetrics


class CodeBugsResponse(BaseModel):
    """Potential bug detection response."""

    language: str
    potential_bugs: list[str]
    metrics: ComplexityMetrics


class CodeOptimizationResponse(BaseModel):
    """Optimization suggestion response."""

    language: str
    optimization_suggestions: list[str]
    metrics: ComplexityMetrics


class CodeComplexityResponse(BaseModel):
    """Complexity analysis response."""

    language: str
    complexity_analysis: str
    metrics: ComplexityMetrics
