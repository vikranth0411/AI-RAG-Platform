from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.chat import ChatMessage, ChatRequest
from app.schemas.rag import RetrievedChunk, RetrievalResponse
from app.services.chat_service import ChatService


@pytest.fixture
def current_user() -> User:
    """Return a lightweight user object for service calls."""
    return User(id=uuid4(), email="user@example.com", hashed_password="hashed")


@pytest.fixture
def service() -> ChatService:
    """Build ChatService with async dependencies replaced by mocks."""
    return ChatService(
        llm_service=Mock(chat=AsyncMock(), stream_chat=Mock()),
        file_repository=Mock(),
        conversation_service=Mock(
            get_conversation=AsyncMock(),
            get_chat_history=AsyncMock(return_value=[]),
            add_user_message=AsyncMock(),
            add_assistant_message=AsyncMock(),
        ),
    )


@pytest.mark.asyncio
async def test_chat_without_conversation_or_rag_uses_request_inputs(
    service: ChatService,
    current_user: User,
) -> None:
    """Stateless chat passes context and supplied history through to the LLM."""
    history = [ChatMessage(role="user", content="Earlier question")]
    service.llm_service.chat.return_value = "Answer"
    payload = ChatRequest(
        message="Question",
        context="  supplied context  ",
        history=history,
        use_rag=False,
    )

    response = await service.chat(payload=payload, current_user=current_user)

    assert response.message == "Answer"
    assert response.context == "supplied context"
    assert response.sources == []
    service.llm_service.chat.assert_awaited_once_with(
        message="Question", context="supplied context", history=history
    )
    service.conversation_service.add_user_message.assert_not_awaited()
    service.conversation_service.add_assistant_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_does_not_initialize_rag_when_disabled(
    service: ChatService,
    current_user: User,
) -> None:
    """Disabled RAG skips both RAG constructors and still calls the LLM."""
    service.llm_service.chat.return_value = "Answer"
    payload = ChatRequest(message="Question", use_rag=False)

    with (
        patch("app.services.chat_service.RAGService") as rag_class,
        patch("app.services.chat_service.VectorStoreService") as vector_store_class,
    ):
        response = await service.chat(payload=payload, current_user=current_user)

    rag_class.assert_not_called()
    vector_store_class.assert_not_called()
    service.llm_service.chat.assert_awaited_once_with(
        message="Question", context="", history=[]
    )
    assert response.message == "Answer"


@pytest.mark.asyncio
async def test_chat_with_conversation_loads_and_persists_messages(
    service: ChatService,
    current_user: User,
) -> None:
    """Conversation chat adds the request and generated reply to persistence."""
    conversation_id = uuid4()
    previous = ChatMessage(role="assistant", content="Prior answer")
    service.conversation_service.get_chat_history.return_value = [previous]
    service.llm_service.chat.return_value = "New answer"
    payload = ChatRequest(
        message="Follow-up", conversation_id=conversation_id, use_rag=False
    )

    response = await service.chat(payload=payload, current_user=current_user)

    service.conversation_service.get_conversation.assert_awaited_once_with(
        conversation_id=conversation_id, current_user=current_user
    )
    service.conversation_service.add_user_message.assert_awaited_once_with(
        conversation_id=conversation_id, current_user=current_user, content="Follow-up"
    )
    service.llm_service.chat.assert_awaited_once_with(
        message="Follow-up",
        context="",
        history=[previous, ChatMessage(role="user", content="Follow-up")],
    )
    service.conversation_service.add_assistant_message.assert_awaited_once_with(
        conversation_id=conversation_id, current_user=current_user, content="New answer"
    )
    assert response.message == "New answer"


@pytest.mark.asyncio
async def test_chat_combines_explicit_context_and_rag_sources(
    service: ChatService,
    current_user: User,
) -> None:
    """Explicit context precedes retrieved context and retrieved sources are returned."""
    chunk = RetrievedChunk(
        id="chunk-1", text="Retrieved passage", score=0.9, metadata={"source": "doc"}
    )
    retrieval = RetrievalResponse(
        query="Question", context="Retrieved passage", results=[chunk]
    )
    rag_service = Mock(retrieve=AsyncMock(return_value=retrieval))
    service.llm_service.chat.return_value = "Answer"
    payload = ChatRequest(message="Question", context=" Explicit passage ", top_k=3)

    with (
        patch("app.services.chat_service.VectorStoreService") as vector_store_class,
        patch("app.services.chat_service.RAGService", return_value=rag_service) as rag_class,
    ):
        response = await service.chat(payload=payload, current_user=current_user)

    vector_store_class.assert_called_once_with()
    rag_class.assert_called_once_with(
        file_repository=service.file_repository,
        vector_store_service=vector_store_class.return_value,
    )
    rag_service.retrieve.assert_awaited_once_with(
        query="Question", top_k=3, current_user=current_user
    )
    assert response.context == "Explicit passage\n\nRetrieved passage"
    assert response.sources == [chunk]
    service.llm_service.chat.assert_awaited_once_with(
        message="Question", context=response.context, history=[]
    )


@pytest.mark.asyncio
async def test_chat_with_empty_rag_keeps_explicit_context_and_no_sources(
    service: ChatService,
    current_user: User,
) -> None:
    """Empty retrieval does not erase explicit context or fabricate sources."""
    rag_service = Mock(
        retrieve=AsyncMock(
            return_value=RetrievalResponse(query="Question", context="", results=[])
        )
    )
    service.llm_service.chat.return_value = "Answer"
    payload = ChatRequest(message="Question", context="Explicit", use_rag=True)

    with (
        patch("app.services.chat_service.VectorStoreService"),
        patch("app.services.chat_service.RAGService", return_value=rag_service),
    ):
        response = await service.chat(payload=payload, current_user=current_user)

    assert response.context == "Explicit"
    assert response.sources == []
    service.llm_service.chat.assert_awaited_once_with(
        message="Question", context="Explicit", history=[]
    )


@pytest.mark.asyncio
async def test_missing_conversation_stops_before_llm(
    service: ChatService,
    current_user: User,
) -> None:
    """Conversation access errors propagate without attempting generation."""
    error = AppError("Conversation not found", code="conversation_not_found")
    service.conversation_service.get_conversation.side_effect = error
    payload = ChatRequest(message="Question", conversation_id=uuid4(), use_rag=False)

    with pytest.raises(AppError) as raised:
        await service.chat(payload=payload, current_user=current_user)

    assert raised.value is error
    service.llm_service.chat.assert_not_awaited()
    service.conversation_service.add_user_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_llm_failure_does_not_persist_assistant_reply(
    service: ChatService,
    current_user: User,
) -> None:
    """Generation failure propagates after preparation has saved the user turn."""
    conversation_id = uuid4()
    failure = AppError("LLM unavailable", code="llm_generation_error")
    service.llm_service.chat.side_effect = failure
    payload = ChatRequest(message="Question", conversation_id=conversation_id, use_rag=False)

    with pytest.raises(AppError) as raised:
        await service.chat(payload=payload, current_user=current_user)

    assert raised.value is failure
    service.conversation_service.add_user_message.assert_awaited_once_with(
        conversation_id=conversation_id, current_user=current_user, content="Question"
    )
    service.conversation_service.add_assistant_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_chat_yields_tokens_and_persists_combined_response(
    service: ChatService,
    current_user: User,
) -> None:
    """Streaming yields tokens in order and persists their concatenation at completion."""
    conversation_id = uuid4()

    async def token_stream() -> AsyncIterator[str]:
        yield "Hello"
        yield " world"

    service.llm_service.stream_chat.return_value = token_stream()
    payload = ChatRequest(message="Question", conversation_id=conversation_id, use_rag=False)
    prepared = SimpleNamespace(context="context", history=[], conversation_id=conversation_id)

    stream = service.stream_chat(payload=payload, prepared=prepared, current_user=current_user)

    assert await anext(stream) == "Hello"
    service.conversation_service.add_assistant_message.assert_not_awaited()

    assert await anext(stream) == " world"
    service.conversation_service.add_assistant_message.assert_not_awaited()

    with pytest.raises(StopAsyncIteration):
        await anext(stream)

    service.llm_service.stream_chat.assert_called_once_with(
        message="Question", context="context", history=[]
    )
    service.conversation_service.add_assistant_message.assert_awaited_once_with(
        conversation_id=conversation_id,
        current_user=current_user,
        content="Hello world",
    )
    service.conversation_service.add_assistant_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_failure_does_not_persist_assistant_reply(
    service: ChatService,
    current_user: User,
) -> None:
    """A stream error propagates and prevents saving an incomplete assistant response."""
    conversation_id = uuid4()
    failure = AppError("Stream failed", code="llm_streaming_error")

    async def failing_stream() -> AsyncIterator[str]:
        yield "Partial"
        raise failure

    service.llm_service.stream_chat.return_value = failing_stream()
    payload = ChatRequest(message="Question", conversation_id=conversation_id, use_rag=False)
    prepared = SimpleNamespace(context="", history=[], conversation_id=conversation_id)

    with pytest.raises(AppError) as raised:
        async for _ in service.stream_chat(
            payload=payload, prepared=prepared, current_user=current_user
        ):
            pass

    assert raised.value is failure
    service.conversation_service.add_assistant_message.assert_not_awaited()
