"""
PDF ingestion pipeline.

Flow:
    PDF file → per-page text extraction → recursive chunking → ChromaDB upsert

Embeddings are handled exclusively by ChromaDB's built-in DefaultEmbeddingFunction
(all-MiniLM-L6-v2, runs locally, no external API required). This keeps the
ingestion pipeline self-contained and ensures the embedding model used at ingest
time is identical to the one used at retrieval time — a mismatch here is the
most common cause of poor RAG retrieval quality.

Metadata stored per chunk:
    doc_id, source_file, page_number, chunk_index, total_chunks,
    ingested_at, file_hash — enough to rebuild provenance and detect stale docs.
"""
from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

from app.core.logging import get_logger
from app.knowledge.chunker import RecursiveChunker

logger = get_logger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class PageContent:
    page_number: int  # 1-based
    text: str


@dataclass
class ChunkRecord:
    chunk_id: str
    content: str
    metadata: dict


@dataclass
class IngestionResult:
    doc_id: str
    source_file: str
    pages_extracted: int
    chunks_stored: int
    file_hash: str
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors


# ── PDF extractor ─────────────────────────────────────────────────────────────


class PDFExtractor:
    """Extracts text from each page of a PDF, running pypdf in a thread."""

    async def extract(self, path: Path) -> list[PageContent]:
        return await asyncio.to_thread(self._extract_sync, path)

    @staticmethod
    def _extract_sync(path: Path) -> list[PageContent]:
        reader = PdfReader(str(path))
        pages: list[PageContent] = []
        for i, page in enumerate(reader.pages):
            raw = page.extract_text() or ""
            text = raw.strip()
            if text:
                pages.append(PageContent(page_number=i + 1, text=text))
        return pages


# ── Ingestion pipeline ────────────────────────────────────────────────────────


class DocumentIngestionPipeline:
    """
    Orchestrates: extract → chunk → store.

    Embeddings are intentionally NOT generated here. ChromaDB's
    DefaultEmbeddingFunction (all-MiniLM-L6-v2) embeds documents at upsert
    time and queries at search time — the same model, guaranteed consistent.

    Accepts a `store_fn` callable so the pipeline stays independent of the
    ChromaDB client — pass `ChromaKnowledgeBase().ingest_chunks_batch`.
    """

    def __init__(
        self,
        store_fn,  # async (records: list[ChunkRecord]) -> None
        chunk_size: int = 800,
        overlap: int = 100,
    ) -> None:
        self._store = store_fn
        self._chunker = RecursiveChunker(chunk_size=chunk_size, overlap=overlap)
        self._extractor = PDFExtractor()

    async def ingest_pdf(
        self,
        path: Path,
        doc_id: str | None = None,
        extra_metadata: dict | None = None,
    ) -> IngestionResult:
        path = Path(path).resolve()
        if not path.exists():
            return IngestionResult(
                doc_id=doc_id or path.stem,
                source_file=str(path),
                pages_extracted=0,
                chunks_stored=0,
                file_hash="",
                errors=[f"File not found: {path}"],
            )

        doc_id = doc_id or path.stem
        file_hash = _hash_file(path)
        ingested_at = datetime.now(tz=timezone.utc).isoformat()
        extra = extra_metadata or {}

        logger.info("ingestion_start", doc_id=doc_id, path=str(path))

        pages = await self._extractor.extract(path)
        if not pages:
            return IngestionResult(
                doc_id=doc_id,
                source_file=path.name,
                pages_extracted=0,
                chunks_stored=0,
                file_hash=file_hash,
                errors=["No text extracted — PDF may be scanned or encrypted"],
            )

        records = self._build_chunk_records(
            pages=pages,
            doc_id=doc_id,
            source_file=path.name,
            file_hash=file_hash,
            ingested_at=ingested_at,
            extra=extra,
        )

        await self._store(records)

        logger.info(
            "ingestion_complete",
            doc_id=doc_id,
            pages=len(pages),
            chunks=len(records),
        )
        return IngestionResult(
            doc_id=doc_id,
            source_file=path.name,
            pages_extracted=len(pages),
            chunks_stored=len(records),
            file_hash=file_hash,
        )

    async def ingest_directory(
        self,
        dir_path: Path,
        pattern: str = "**/*.pdf",
        extra_metadata: dict | None = None,
    ) -> list[IngestionResult]:
        pdf_files = sorted(Path(dir_path).glob(pattern))
        if not pdf_files:
            logger.warning("no_pdfs_found", directory=str(dir_path), pattern=pattern)
            return []

        results: list[IngestionResult] = []
        for pdf in pdf_files:
            result = await self.ingest_pdf(pdf, extra_metadata=extra_metadata)
            results.append(result)
            status = "ok" if result.success else "error"
            logger.info("file_ingested", file=pdf.name, status=status, chunks=result.chunks_stored)

        return results

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_chunk_records(
        self,
        pages: list[PageContent],
        doc_id: str,
        source_file: str,
        file_hash: str,
        ingested_at: str,
        extra: dict,
    ) -> list[ChunkRecord]:
        records: list[ChunkRecord] = []
        global_idx = 0

        for page in pages:
            chunks = self._chunker.chunk(page.text)
            for chunk_text in chunks:
                chunk_id = f"{doc_id}::p{page.page_number}::c{global_idx}"
                metadata = {
                    "doc_id": doc_id,
                    "source_file": source_file,
                    "page_number": page.page_number,
                    "chunk_index": global_idx,
                    "file_hash": file_hash,
                    "ingested_at": ingested_at,
                    **extra,
                }
                records.append(ChunkRecord(chunk_id=chunk_id, content=chunk_text, metadata=metadata))
                global_idx += 1

        for record in records:
            record.metadata["total_chunks"] = global_idx

        return records


# ── Helpers ───────────────────────────────────────────────────────────────────


def _hash_file(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()
