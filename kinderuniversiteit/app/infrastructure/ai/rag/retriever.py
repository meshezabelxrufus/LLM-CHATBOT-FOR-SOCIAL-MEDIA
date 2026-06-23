"""
Semantic retrieval from ChromaDB.

RetrievedChunk carries everything the AI service needs to build a grounded
response: the text, its similarity score, and the full provenance metadata
(source file, page number, doc_id).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.core.constants import RAG_SIMILARITY_THRESHOLD, RAG_TOP_K
from app.core.logging import get_logger

from app.infrastructure.ai.rag.vector_store import get_chroma_collection

logger = get_logger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    content: str
    similarity: float
    metadata: dict

    @property
    def source_file(self) -> str:
        return self.metadata.get("source_file", "unknown")

    @property
    def page_number(self) -> int | None:
        return self.metadata.get("page_number")

    @property
    def doc_id(self) -> str:
        return self.metadata.get("doc_id", self.chunk_id)


class Retriever:
    def __init__(
        self,
        similarity_threshold: float = RAG_SIMILARITY_THRESHOLD,
    ) -> None:
        self._threshold = similarity_threshold

    async def retrieve(
        self,
        query: str,
        top_k: int = RAG_TOP_K,
        where: dict | None = None,
    ) -> list[RetrievedChunk]:
        """
        Embed `query`, query ChromaDB, return chunks above the similarity threshold.

        `where` is an optional ChromaDB metadata filter, e.g. {"doc_id": "faq-v1"}.
        Results are sorted by similarity descending.
        """
        query_kwargs: dict = dict(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        if where:
            query_kwargs["where"] = where

        collection = await asyncio.to_thread(get_chroma_collection)
        raw = await asyncio.to_thread(collection.query, **query_kwargs)

        chunks = self._parse_results(raw)
        filtered = [c for c in chunks if c.similarity >= self._threshold]

        logger.info(
            "retrieval_complete",
            query_len=len(query),
            returned=len(chunks),
            above_threshold=len(filtered),
            threshold=self._threshold,
        )
        return filtered

    async def retrieve_as_context(
        self,
        query: str,
        top_k: int = RAG_TOP_K,
        where: dict | None = None,
    ) -> str:
        """
        Convenience method: returns a single formatted string ready to be
        injected into a prompt as retrieved context.
        """
        chunks = await self.retrieve(query, top_k=top_k, where=where)
        if not chunks:
            return ""
        parts = []
        for chunk in chunks:
            source = f"{chunk.source_file}"
            if chunk.page_number:
                source += f", page {chunk.page_number}"
            parts.append(f"[Source: {source}]\n{chunk.content}")
        return "\n\n---\n\n".join(parts)

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_results(raw) -> list[RetrievedChunk]:
        ids = raw.get("ids", [[]])[0]
        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        chunks: list[RetrievedChunk] = []
        for chunk_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite.
            # Convert to a 0–1 similarity score.
            similarity = max(0.0, 1.0 - dist)
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    content=doc,
                    similarity=round(similarity, 4),
                    metadata=meta or {},
                )
            )

        return sorted(chunks, key=lambda c: c.similarity, reverse=True)
