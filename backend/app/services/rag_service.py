import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import status
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import CSVLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.uploaded_file import UploadedFile
from app.models.user import User
from app.repositories.file_repository import FileRepository
from app.schemas.rag import IngestResponse, RetrievedChunk, RetrievalResponse, SearchResponse
from app.services.vector_store_service import Metadata, VectorStoreService


class RAGService:
    """Retrieval-augmented generation pipeline orchestration."""

    def __init__(
        self,
        *,
        file_repository: FileRepository,
        vector_store_service: VectorStoreService,
    ) -> None:
        self.file_repository = file_repository
        self.vector_store_service = vector_store_service
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""],
        )

    async def ingest_uploaded_file(self, *, file_id: UUID, current_user: User) -> IngestResponse:
        """Load, chunk, embed, and index an uploaded file."""
        uploaded_file = await self.file_repository.get_owned_file(
            file_id=file_id,
            owner_id=current_user.id,
        )
        if not uploaded_file:
            raise AppError(
                "Uploaded file not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="file_not_found",
            )

        documents = await asyncio.to_thread(self._load_uploaded_file, uploaded_file)
        chunks = self.text_splitter.split_documents(documents)
        return await self._index_chunks(
            chunks=chunks,
            source_id=str(uploaded_file.id),
            source_name=uploaded_file.original_filename,
            current_user=current_user,
            base_metadata={
                "source_type": "uploaded_file",
                "file_id": str(uploaded_file.id),
                "filename": uploaded_file.original_filename,
                "extension": uploaded_file.file_extension,
            },
        )

    async def ingest_text(
        self,
        *,
        text: str,
        source_name: str,
        current_user: User,
    ) -> IngestResponse:
        """Chunk, embed, and index raw text."""
        source_id = uuid4().hex
        documents = [Document(page_content=text, metadata={"source": source_name})]
        chunks = self.text_splitter.split_documents(documents)
        return await self._index_chunks(
            chunks=chunks,
            source_id=source_id,
            source_name=source_name,
            current_user=current_user,
            base_metadata={
                "source_type": "text",
                "source_name": source_name,
            },
        )

    async def semantic_search(
        self,
        *,
        query: str,
        top_k: int,
        current_user: User,
    ) -> SearchResponse:
        """Run user-scoped semantic search over indexed chunks."""
        results = await self.vector_store_service.semantic_search(
            query=query,
            top_k=top_k,
            where={"owner_id": str(current_user.id)},
        )
        return SearchResponse(
            query=query,
            results=[RetrievedChunk(**result) for result in results],
        )

    async def retrieve(
        self,
        *,
        query: str,
        top_k: int,
        current_user: User,
    ) -> RetrievalResponse:
        """Run the retrieval stage and return concatenated context for generation."""
        search_response = await self.semantic_search(
            query=query,
            top_k=top_k,
            current_user=current_user,
        )
        context = "\n\n".join(result.text for result in search_response.results)
        return RetrievalResponse(query=query, context=context, results=search_response.results)

    async def _index_chunks(
        self,
        *,
        chunks: list[Document],
        source_id: str,
        source_name: str,
        current_user: User,
        base_metadata: Metadata,
    ) -> IngestResponse:
        """Store chunk embeddings and metadata in the vector database."""
        if not chunks:
            raise AppError(
                "No text content found for indexing",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="empty_document",
            )

        ids: list[str] = []
        texts: list[str] = []
        metadatas: list[Metadata] = []
        for index, chunk in enumerate(chunks):
            chunk_text = chunk.page_content.strip()
            if not chunk_text:
                continue
            ids.append(f"{source_id}:{index}")
            texts.append(chunk_text)
            metadatas.append(
                {
                    **base_metadata,
                    "owner_id": str(current_user.id),
                    "source_id": source_id,
                    "source_name": source_name,
                    "chunk_index": index,
                }
            )

        chunks_indexed = await self.vector_store_service.add_texts(
            ids=ids,
            texts=texts,
            metadatas=metadatas,
        )
        return IngestResponse(source_id=source_id, chunks_indexed=chunks_indexed)

    def _load_uploaded_file(self, uploaded_file: UploadedFile) -> list[Document]:
        """Load an uploaded file with an appropriate LangChain loader."""
        path = Path(uploaded_file.storage_path)
        if not path.exists():
            raise AppError(
                "Stored file is missing",
                status_code=status.HTTP_404_NOT_FOUND,
                code="stored_file_missing",
            )

        extension = uploaded_file.file_extension.lower()
        if extension == "pdf":
            loader = PyPDFLoader(str(path))
        elif extension == "csv":
            loader = CSVLoader(str(path), encoding="utf-8")
        elif extension == "json":
            with path.open(encoding="utf-8") as file:
                payload = json.load(file)
            return [
                Document(
                    page_content=json.dumps(payload, ensure_ascii=False, indent=2),
                    metadata={"source": uploaded_file.original_filename},
                )
            ]
        else:
            loader = TextLoader(str(path), encoding="utf-8", autodetect_encoding=True)
        return loader.load()
