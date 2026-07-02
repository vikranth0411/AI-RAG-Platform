from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Message, MessageRole


class MessageRepository:
    """Database access layer for conversation messages."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
    ) -> Message:
        """Persist and return a new conversation message."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def list_by_conversation(self, conversation_id: UUID) -> list[Message]:
        """Return messages for a conversation, oldest first."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    async def delete(self, message: Message) -> None:
        """Delete a conversation message."""
        await self.db.delete(message)
        await self.db.commit()
