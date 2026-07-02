from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat import ChatMessage


class ConversationCreateRequest(BaseModel):
    """Request payload for creating a conversation."""

    title: str | None = Field(default=None, max_length=255)


class ConversationResponse(BaseModel):
    """Public conversation representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """Response payload containing conversations owned by the user."""

    conversations: list[ConversationResponse]


class ConversationMessagesResponse(BaseModel):
    """Response payload containing chat messages for a conversation."""

    messages: list[ChatMessage]
