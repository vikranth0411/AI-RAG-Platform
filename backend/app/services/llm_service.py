from collections.abc import AsyncIterator

from fastapi import status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq

from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.chat import ChatMessage

CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a precise AI assistant for the AI RAG Platform. "
            "Use the supplied context when it is relevant. If the context does not contain "
            "the answer, say what is missing and answer from general knowledge only when safe.\n\n"
            "Context:\n{context}",
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{message}"),
    ]
)


class LLMService:
    """Groq Llama chat integration with prompt templating and streaming."""

    def __init__(self) -> None:
        if not settings.GROQ_API_KEY:
            raise AppError(
                "GROQ_API_KEY is not configured",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="llm_not_configured",
            )

        self.model = ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            temperature=settings.GROQ_TEMPERATURE,
            max_tokens=settings.GROQ_MAX_TOKENS,
        )
        self.chain = CHAT_PROMPT | self.model | StrOutputParser()

    async def chat(
        self,
        *,
        message: str,
        context: str,
        history: list[ChatMessage],
    ) -> str:
        """Generate a full chat response from Groq."""
        try:
            return await self.chain.ainvoke(
                {
                    "message": message,
                    "context": context,
                    "history": self._to_langchain_history(history),
                }
            )
        except Exception as exc:
            raise AppError(
                "LLM generation failed",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="llm_generation_error",
            ) from exc

    async def stream_chat(
        self,
        *,
        message: str,
        context: str,
        history: list[ChatMessage],
    ) -> AsyncIterator[str]:
        """Stream a chat response token-by-token from Groq."""
        try:
            async for chunk in self.chain.astream(
                {
                    "message": message,
                    "context": context,
                    "history": self._to_langchain_history(history),
                }
            ):
                if chunk:
                    yield chunk
        except Exception as exc:
            raise AppError(
                "LLM streaming failed",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="llm_streaming_error",
            ) from exc

    def _to_langchain_history(self, history: list[ChatMessage]) -> list[BaseMessage]:
        """Convert API chat history into LangChain message objects."""
        messages: list[BaseMessage] = []
        for item in history:
            if item.role == "assistant":
                messages.append(AIMessage(content=item.content))
            elif item.role == "system":
                messages.append(SystemMessage(content=item.content))
            else:
                messages.append(HumanMessage(content=item.content))
        return messages
