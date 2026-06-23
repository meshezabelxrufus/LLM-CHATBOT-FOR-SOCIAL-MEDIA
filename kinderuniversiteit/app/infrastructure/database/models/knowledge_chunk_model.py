"""SQLAlchemy ORM model for the knowledge_chunks table.

Stores per-chunk metadata alongside the knowledge_documents row.
The actual embedding vectors live in ChromaDB — this table provides a
relational view of what was chunked, useful for admin UIs and auditing.

chunk_id must match the ID used in ChromaDB:
  format → {doc_id}::p{page_number}::c{chunk_index}
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class KnowledgeChunkModel(Base):
    __tablename__ = "knowledge_chunks"

    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_knowledge_chunks_chunk_id"),
        # Positional uniqueness: one chunk per (document, page, index) triple.
        UniqueConstraint(
            "document_id", "page_number", "chunk_index",
            name="uq_knowledge_chunks_position",
        ),
        Index("ix_knowledge_chunks_document_id", "document_id"),
        Index("ix_knowledge_chunks_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Must match the chunk ID stored in ChromaDB.
    chunk_id: Mapped[str] = mapped_column(String(500), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # First 500 chars of content — shown in admin UI without hitting ChromaDB.
    content_preview: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped["KnowledgeDocumentModel"] = relationship(  # noqa: F821
        back_populates="chunks"
    )
