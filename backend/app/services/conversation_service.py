from uuid import UUID

from fastapi import status

from app.core.exceptions import AppError
from app.models.conversation import Conversation, Message, MessageRole
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.chat import ChatMessage


class ConversationService:
    """Business service for managing user conversations and messages."""

    def __init__(
        self,
        *,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
    ) -> None:
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository

    async def create_conversation(
        self,
        current_user: User,
        title: str | None = None,
    ) -> Conversation:
        """Create a new conversation for a user."""
        return await self.conversation_repository.create(
            owner_id=current_user.id,
            title=title if title is not None else "New Chat",
        )

    async def list_conversations(self, current_user: User) -> list[Conversation]:
        """Return conversations owned by a user."""
        return await self.conversation_repository.list_by_owner(current_user.id)

    async def get_conversation(
        self,
        conversation_id: UUID,
        current_user: User,
    ) -> Conversation:
        """Return a conversation after validating ownership."""
        conversation = await self.conversation_repository.get_by_id(
            conversation_id=conversation_id,
            owner_id=current_user.id,
        )
        if not conversation:
            raise AppError(
                message="Conversation not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="conversation_not_found",
            )
        return conversation

    async def delete_conversation(
        self,
        conversation_id: UUID,
        current_user: User,
    ) -> None:
        """Delete a conversation after validating ownership."""
        conversation = await self.get_conversation(
            conversation_id=conversation_id,
            current_user=current_user,
        )
        await self.conversation_repository.delete(conversation)

    async def add_user_message(
        self,
        conversation_id: UUID,
        current_user: User,
        content: str,
    ) -> Message:
        """Add a user message to an owned conversation."""
        await self.get_conversation(
            conversation_id=conversation_id,
            current_user=current_user,
        )
        return await self.message_repository.create(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=content,
        )

    async def add_assistant_message(
        self,
        conversation_id: UUID,
        current_user: User,
        content: str,
    ) -> Message:
        """Add an assistant message to an owned conversation."""
        await self.get_conversation(
            conversation_id=conversation_id,
            current_user=current_user,
        )
        return await self.message_repository.create(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
        )

    async def get_chat_history(
        self,
        conversation_id: UUID,
        current_user: User,
    ) -> list[ChatMessage]:
        """Return an owned conversation's messages as chat history."""
        await self.get_conversation(
            conversation_id=conversation_id,
            current_user=current_user,
        )
        messages = await self.message_repository.list_by_conversation(conversation_id)
        return [
            ChatMessage(role=message.role, content=message.content)
            for message in messages
        ]
