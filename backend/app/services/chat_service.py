from collections.abc import AsyncIterator
from uuid import UUID

from app.models.user import User
from app.repositories.file_repository import FileRepository
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse
from app.schemas.rag import RetrievedChunk
from app.services.conversation_service import ConversationService
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.services.vector_store_service import VectorStoreService


class PreparedChat:
    """Prepared prompt inputs for chat generation."""

    def __init__(
        self,
        *,
        context: str,
        sources: list[RetrievedChunk],
        history: list[ChatMessage],
        conversation_id: UUID | None,
    ) -> None:
        self.context = context
        self.sources = sources
        self.history = history
        self.conversation_id = conversation_id


class ChatService:
    """Chat orchestration with prompt context injection and optional RAG retrieval."""

    def __init__(
        self,
        *,
        llm_service: LLMService,
        file_repository: FileRepository,
        conversation_service: ConversationService,
    ) -> None:
        self.llm_service = llm_service
        self.file_repository = file_repository
        self.conversation_service = conversation_service

    async def chat(self, *, payload: ChatRequest, current_user: User) -> ChatResponse:
        """Generate a complete chat response."""
        prepared = await self.prepare_chat(payload=payload, current_user=current_user)
        message = await self.llm_service.chat(
            message=payload.message,
            context=prepared.context,
            history=prepared.history,
        )
        if prepared.conversation_id:
            await self.conversation_service.add_assistant_message(
                conversation_id=prepared.conversation_id,
                current_user=current_user,
                content=message,
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
        history = payload.history

        if payload.conversation_id:
            await self.conversation_service.get_conversation(
                conversation_id=payload.conversation_id,
                current_user=current_user,
            )
            history = await self.conversation_service.get_chat_history(
                conversation_id=payload.conversation_id,
                current_user=current_user,
            )
            await self.conversation_service.add_user_message(
                conversation_id=payload.conversation_id,
                current_user=current_user,
                content=payload.message,
            )
            history.append(ChatMessage(role="user", content=payload.message))

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
            history=history,
            conversation_id=payload.conversation_id,
        )

    async def stream_chat(
        self,
        *,
        payload: ChatRequest,
        prepared: PreparedChat,
        current_user: User,
    ) -> AsyncIterator[str]:
        """Stream a chat response using already prepared context."""
        chunks: list[str] = []
        async for token in self.llm_service.stream_chat(
            message=payload.message,
            context=prepared.context,
            history=prepared.history,
        ):
            chunks.append(token)
            yield token
        if prepared.conversation_id:
            await self.conversation_service.add_assistant_message(
                conversation_id=prepared.conversation_id,
                current_user=current_user,
                content="".join(chunks),
            )
