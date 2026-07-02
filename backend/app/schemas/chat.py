from uuid import UUID

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.rag import RetrievedChunk


class ChatMessage(BaseModel):
    """Prior conversation message used for prompt history."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    """Chat completion request with optional RAG context injection."""

    message: str = Field(..., min_length=1)
    conversation_id: UUID | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    context: str | None = None
    use_rag: bool = True
    top_k: int = Field(default=settings.RAG_DEFAULT_TOP_K, ge=1, le=20)


class ChatResponse(BaseModel):
    """Chat completion response."""

    message: str
    context: str
    sources: list[RetrievedChunk]


class StreamChunk(BaseModel):
    """Server-sent event chunk payload."""

    token: str
