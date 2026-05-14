from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.file_repository import FileRepository
from app.schemas.rag import (
    IngestFileRequest,
    IngestResponse,
    IngestTextRequest,
    RetrievalResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.rag_service import RAGService
from app.services.vector_store_service import VectorStoreService

router = APIRouter()


def get_rag_service(db: AsyncSession = Depends(get_db)) -> RAGService:
    """Provide a RAG service wired to persistence and vector storage."""
    return RAGService(
        file_repository=FileRepository(db),
        vector_store_service=VectorStoreService(),
    )


@router.post("/ingest/file", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_file(
    payload: IngestFileRequest,
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
) -> IngestResponse:
    """Index an uploaded file into the vector store."""
    return await rag_service.ingest_uploaded_file(
        file_id=payload.file_id,
        current_user=current_user,
    )


@router.post("/ingest/text", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_text(
    payload: IngestTextRequest,
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
) -> IngestResponse:
    """Index raw text into the vector store."""
    return await rag_service.ingest_text(
        text=payload.text,
        source_name=payload.source_name,
        current_user=current_user,
    )


@router.post("/search", response_model=SearchResponse, status_code=status.HTTP_200_OK)
async def semantic_search(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
) -> SearchResponse:
    """Run semantic search over the authenticated user's indexed chunks."""
    return await rag_service.semantic_search(
        query=payload.query,
        top_k=payload.top_k,
        current_user=current_user,
    )


@router.post("/retrieve", response_model=RetrievalResponse, status_code=status.HTTP_200_OK)
async def retrieve_context(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
) -> RetrievalResponse:
    """Run the retrieval pipeline and return context for answer generation."""
    return await rag_service.retrieve(
        query=payload.query,
        top_k=payload.top_k,
        current_user=current_user,
    )


@router.post("/query", response_model=RetrievalResponse, status_code=status.HTTP_200_OK)
async def query_rag(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
) -> RetrievalResponse:
    """Run the RAG retrieval pipeline for a user query."""
    return await rag_service.retrieve(
        query=payload.query,
        top_k=payload.top_k,
        current_user=current_user,
    )


@router.get("/status", status_code=status.HTTP_200_OK)
async def rag_status() -> dict[str, str]:
    """Return RAG module implementation status."""
    return {"module": "rag", "status": "implemented"}
