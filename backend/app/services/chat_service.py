from collections.abc import AsyncIterator

from app.models.user import User
from app.repositories.file_repository import FileRepository
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.rag import RetrievedChunk
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.services.vector_store_service import VectorStoreService


class PreparedChat:
    """Prepared prompt inputs for chat generation."""

    def __init__(self, *, context: str, sources: list[RetrievedChunk]) -> None:
        self.context = context
        self.sources = sources


class ChatService:
    """Chat orchestration with prompt context injection and optional RAG retrieval."""

    def __init__(
        self,
        *,
        llm_service: LLMService,
        file_repository: FileRepository,
    ) -> None:
        self.llm_service = llm_service
        self.file_repository = file_repository

    async def chat(self, *, payload: ChatRequest, current_user: User) -> ChatResponse:
        """Generate a complete chat response."""
        prepared = await self.prepare_chat(payload=payload, current_user=current_user)
        message = await self.llm_service.chat(
            message=payload.message,
            context=prepared.context,
            history=payload.history,
        )
        return ChatResponse(
            message=message,
            context=prepared.context,
            sources=prepared.sources,
        )

    async def prepare_chat(self, *, payload: ChatRequest, current_user: User) -> PreparedChat:
        """Resolve explicit and retrieved context before LLM generation."""
        context_parts: list[str] = []
        sources: list[RetrievedChunk] = []

        if payload.context:
            context_parts.append(payload.context.strip())

        if payload.use_rag:
            rag_service = RAGService(
                file_repository=self.file_repository,
                vector_store_service=VectorStoreService(),
            )
            retrieval = await rag_service.retrieve(
                query=payload.message,
                top_k=payload.top_k,
                current_user=current_user,
            )
            if retrieval.context:
                context_parts.append(retrieval.context)
            sources = retrieval.results

        return PreparedChat(
            context="\n\n".join(part for part in context_parts if part),
            sources=sources,
        )

    async def stream_chat(
        self,
        *,
        payload: ChatRequest,
        prepared: PreparedChat,
    ) -> AsyncIterator[str]:
        """Stream a chat response using already prepared context."""
        async for token in self.llm_service.stream_chat(
            message=payload.message,
            context=prepared.context,
            history=payload.history,
        ):
            yield token
