from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.models.conversation import Conversation
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationMessagesResponse,
    ConversationResponse,
)
from app.services.conversation_service import ConversationService

router = APIRouter()


def get_conversation_service(db: AsyncSession = Depends(get_db)) -> ConversationService:
    """Provide a conversation service wired to persistence dependencies."""
    return ConversationService(
        conversation_repository=ConversationRepository(db),
        message_repository=MessageRepository(db),
    )


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> Conversation:
    """Create a conversation for the authenticated user."""
    return await conversation_service.create_conversation(
        current_user=current_user,
        title=payload.title,
    )


@router.get("", response_model=ConversationListResponse, status_code=status.HTTP_200_OK)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ConversationListResponse:
    """List conversations owned by the authenticated user."""
    conversations = await conversation_service.list_conversations(current_user=current_user)
    return ConversationListResponse(conversations=conversations)


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
)
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> Conversation:
    """Return a single conversation owned by the authenticated user."""
    return await conversation_service.get_conversation(
        conversation_id=conversation_id,
        current_user=current_user,
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_conversation_messages(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ConversationMessagesResponse:
    """Return chat history for an owned conversation."""
    messages = await conversation_service.get_chat_history(
        conversation_id=conversation_id,
        current_user=current_user,
    )
    return ConversationMessagesResponse(messages=messages)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> None:
    """Delete a conversation owned by the authenticated user."""
    await conversation_service.delete_conversation(
        conversation_id=conversation_id,
        current_user=current_user,
    )
