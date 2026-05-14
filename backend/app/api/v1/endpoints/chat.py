import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.exceptions import AppError
from app.models.user import User
from app.repositories.file_repository import FileRepository
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService, PreparedChat
from app.services.llm_service import LLMService

router = APIRouter()


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    """Provide a chat service wired to LLM and persistence dependencies."""
    return ChatService(
        llm_service=LLMService(),
        file_repository=FileRepository(db),
    )


@router.post("/completions", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def create_chat_completion(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """Generate a Groq Llama chat completion with optional context injection."""
    return await chat_service.chat(payload=payload, current_user=current_user)


@router.post("/stream", status_code=status.HTTP_200_OK)
async def stream_chat_completion(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """Stream a Groq Llama chat completion as server-sent events."""
    prepared = await chat_service.prepare_chat(payload=payload, current_user=current_user)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for token in chat_service.stream_chat(payload=payload, prepared=prepared):
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'done': True, 'sources': _serialize_sources(prepared)})}\n\n"
        except AppError as exc:
            error_payload = {"error": {"code": exc.code, "message": exc.message}}
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/status", status_code=status.HTTP_200_OK)
async def chat_status() -> dict[str, str]:
    """Return chat module implementation status."""
    return {"module": "chat", "status": "implemented"}


def _serialize_sources(prepared: PreparedChat) -> list[dict]:
    """Serialize source chunks for the final stream event."""
    return [source.model_dump(mode="json") for source in prepared.sources]
