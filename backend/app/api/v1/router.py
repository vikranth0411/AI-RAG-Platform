from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    chat,
    code_understanding,
    conversations,
    files,
    health,
    nl_sql,
    rag,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(nl_sql.router, prefix="/nl-sql", tags=["natural-language-sql"])
api_router.include_router(
    code_understanding.router,
    prefix="/code-understanding",
    tags=["code-understanding"],
)

