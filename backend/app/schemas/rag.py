from uuid import UUID

from pydantic import BaseModel, Field

from app.core.config import settings


class IngestFileRequest(BaseModel):
    """Request payload for indexing an uploaded file into the vector store."""

    file_id: UUID


class IngestTextRequest(BaseModel):
    """Request payload for indexing raw text into the vector store."""

    text: str = Field(..., min_length=1)
    source_name: str = Field(default="manual-input", min_length=1, max_length=255)


class IngestResponse(BaseModel):
    """Summary of indexed chunks."""

    source_id: str
    chunks_indexed: int


class SearchRequest(BaseModel):
    """Semantic search request."""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=settings.RAG_DEFAULT_TOP_K, ge=1, le=20)


class RetrievedChunk(BaseModel):
    """Single semantic search result."""

    id: str
    text: str
    score: float | None = None
    metadata: dict[str, str | int | float | bool]


class SearchResponse(BaseModel):
    """Semantic search response."""

    query: str
    results: list[RetrievedChunk]


class RetrievalResponse(BaseModel):
    """Retrieval pipeline response with context ready for generation."""

    query: str
    context: str
    results: list[RetrievedChunk]
