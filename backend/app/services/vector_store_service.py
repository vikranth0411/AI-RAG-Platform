import asyncio
from functools import lru_cache
from typing import Any

import chromadb
from fastapi import status
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.exceptions import AppError

MetadataValue = str | int | float | bool
Metadata = dict[str, MetadataValue]


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load and cache the configured sentence-transformer embedding model."""
    return SentenceTransformer(settings.EMBEDDING_MODEL)


class VectorStoreService:
    """ChromaDB-backed vector store for document chunks."""

    def __init__(self) -> None:
        try:
            self.client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
            self.collection = self.client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise AppError(
                "Vector store is unavailable",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="vector_store_unavailable",
            ) from exc

    async def add_texts(
        self,
        *,
        ids: list[str],
        texts: list[str],
        metadatas: list[Metadata],
    ) -> int:
        """Embed and store text chunks in ChromaDB."""
        if not texts:
            return 0

        try:
            embeddings = await asyncio.to_thread(self._embed_documents, texts)
            await asyncio.to_thread(
                self.collection.upsert,
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except Exception as exc:
            raise AppError(
                "Vector store indexing failed",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="vector_store_error",
            ) from exc
        return len(texts)

    async def semantic_search(
        self,
        *,
        query: str,
        top_k: int,
        where: Metadata | None = None,
    ) -> list[dict[str, Any]]:
        """Search ChromaDB for chunks semantically similar to the query."""
        embedding = await asyncio.to_thread(self._embed_query, query)
        try:
            result = await asyncio.to_thread(
                self.collection.query,
                query_embeddings=[embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise AppError(
                "Vector store search failed",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="vector_store_error",
            ) from exc

        return self._normalize_query_result(result)

    def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Create dense vectors for document chunks."""
        return get_embedding_model().encode(texts, normalize_embeddings=True).tolist()

    def _embed_query(self, query: str) -> list[float]:
        """Create a dense vector for a search query."""
        return get_embedding_model().encode(query, normalize_embeddings=True).tolist()

    def _normalize_query_result(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """Flatten Chroma's batched response into result dictionaries."""
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        normalized: list[dict[str, Any]] = []
        for index, chunk_id in enumerate(ids):
            distance = distances[index] if index < len(distances) else None
            score = 1 - distance if distance is not None else None
            normalized.append(
                {
                    "id": chunk_id,
                    "text": documents[index] if index < len(documents) else "",
                    "metadata": metadatas[index] if index < len(metadatas) else {},
                    "score": score,
                }
            )
        return normalized
