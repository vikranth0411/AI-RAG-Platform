from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation


class ConversationRepository:
    """Database access layer for conversations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, *, owner_id: UUID, title: str) -> Conversation:
        """Persist and return a new conversation."""
        conversation = Conversation(owner_id=owner_id, title=title)
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def get_by_id(
        self,
        *,
        conversation_id: UUID,
        owner_id: UUID,
    ) -> Conversation | None:
        """Return a single conversation owned by a user."""
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_owner(self, owner_id: UUID) -> list[Conversation]:
        """Return conversations owned by a user, newest first."""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.owner_id == owner_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(result.scalars().all())

    async def delete(self, conversation: Conversation) -> None:
        """Delete a conversation."""
        await self.db.delete(conversation)
        await self.db.commit()
