"""ChromaDB client — single collection for the knowledge base.

Two modes controlled by settings:
  Embedded  CHROMA_HOST=""       → PersistentClient (in-process, data/chroma/)
  Remote    CHROMA_HOST="..."    → HttpClient (separate ChromaDB container)

The embedded mode is used for local development and single-server deployments.
The remote mode is used when running ChromaDB as a separate Docker service.
"""
from __future__ import annotations

import asyncio

from typing import cast

import chromadb
from chromadb import ClientAPI, Collection
from chromadb.api.types import EmbeddingFunction
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# paraphrase-multilingual-MiniLM-L12-v2 supports 50+ languages including
# Dutch and English, making it suitable for cross-lingual queries against
# Dutch knowledge-base content. It is downloaded once and cached locally.
_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

_client: ClientAPI | None = None
_collection: Collection | None = None
_embedding_fn: SentenceTransformerEmbeddingFunction | None = None


def _get_embedding_fn() -> SentenceTransformerEmbeddingFunction:
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = SentenceTransformerEmbeddingFunction(model_name=_EMBEDDING_MODEL)
    return _embedding_fn


def get_chroma_client() -> ClientAPI:
    global _client
    if _client is None:
        if settings.chroma_use_embedded:
            persist_path = str(settings.chroma_persist_dir.resolve())
            logger.info("chroma_embedded_mode", path=persist_path)
            _client = chromadb.PersistentClient(path=persist_path)
        else:
            logger.info(
                "chroma_remote_mode",
                host=settings.chroma_host,
                port=settings.chroma_port,
            )
            _client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
            )
    return _client


def get_chroma_collection() -> Collection:
    global _collection
    if _collection is None:
        client = get_chroma_client()
        _collection = client.get_or_create_collection(
            name=settings.chroma_collection_name,
            embedding_function=cast(EmbeddingFunction, _get_embedding_fn()),
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


async def get_chroma_collection_async() -> Collection:
    """Thread-safe async wrapper for use inside FastAPI request handlers."""
    return await asyncio.to_thread(get_chroma_collection)
