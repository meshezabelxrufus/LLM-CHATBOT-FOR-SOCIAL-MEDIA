"""
Concrete IKnowledgeBase backed by ChromaDB.

ingest_document  — single chunk, used by the admin API endpoint.
ingest_chunks_batch — bulk path used by DocumentIngestionPipeline.
delete_document  — removes every chunk whose metadata.doc_id matches.
search           — cosine-similarity retrieval via Retriever.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.application.interfaces.knowledge_base import IKnowledgeBase
from app.core.logging import get_logger
from app.infrastructure.ai.rag.vector_store import get_chroma_collection
from app.knowledge.document_ingestion import ChunkRecord

logger = get_logger(__name__)


class ChromaKnowledgeBase(IKnowledgeBase):
    def __init__(self) -> None:
        pass

    # ── IKnowledgeBase interface ───────────────────────────────────────────────

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        # Import here to avoid circular dependency at module load time.
        from app.infrastructure.ai.rag.retriever import Retriever
        retriever = Retriever()
        chunks = await retriever.retrieve(query, top_k=top_k)
        return [
            {"content": c.content, "metadata": c.metadata, "similarity": c.similarity}
            for c in chunks
        ]

    async def ingest_document(self, doc_id: str, content: str, metadata: dict) -> None:
        """Upsert a single pre-chunked text block.

        No explicit embedding is passed — ChromaDB's built-in DefaultEmbeddingFunction
        (all-MiniLM-L6-v2, local, no API key required) embeds the document automatically.
        This keeps the embedded-mode path dependency-free from external embedding APIs.
        """
        collection = await asyncio.to_thread(get_chroma_collection)
        await asyncio.to_thread(
            collection.upsert,
            ids=[doc_id],
            documents=[content],
            metadatas=[{"doc_id": doc_id, **metadata}],
        )
        logger.info("chunk_upserted", chunk_id=doc_id)

    async def delete_document(self, doc_id: str) -> None:
        """Delete all chunks that were ingested under this doc_id."""
        collection = await asyncio.to_thread(get_chroma_collection)
        await asyncio.to_thread(
            collection.delete,
            where={"doc_id": doc_id},
        )
        logger.info("document_deleted", doc_id=doc_id)

    # ── Batch path (used by DocumentIngestionPipeline) ────────────────────────

    async def ingest_chunks_batch(self, records: list[ChunkRecord]) -> None:
        """
        Upsert a batch of ChunkRecords into ChromaDB.

        Embeddings are NOT passed explicitly — ChromaDB's DefaultEmbeddingFunction
        (all-MiniLM-L6-v2) handles them at upsert time. This guarantees the same
        model is used at ingest and at retrieval (query_texts path), which is
        required for cosine similarity to be meaningful.
        """
        if not records:
            return

        ids = [r.chunk_id for r in records]
        documents = [r.content for r in records]
        metadatas: Any = [r.metadata for r in records]

        collection = await asyncio.to_thread(get_chroma_collection)
        await asyncio.to_thread(
            collection.upsert,
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info("batch_upserted", chunks=len(records))
