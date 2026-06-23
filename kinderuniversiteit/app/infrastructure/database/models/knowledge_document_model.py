"""SQLAlchemy ORM model for the knowledge_documents table.

Tracks every PDF that has been ingested into the vector store.  The actual
embeddings live in ChromaDB; this table stores metadata needed for admin UI,
deduplication, and audit trails.

doc_id matches the identifier stored in ChromaDB metadata so the two stores
can be correlated without a full-table scan.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.knowledge_document_status import KnowledgeDocumentStatus
from app.infrastructure.database.base import Base


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"

    __table_args__ = (
        UniqueConstraint("doc_id", name="uq_knowledge_documents_doc_id"),
        # Deduplication: detect re-uploads of the same file by content hash.
        Index("ix_knowledge_documents_file_hash", "file_hash"),
        Index("ix_knowledge_documents_tenant_status", "tenant_id", "status"),
        # Partial index for active (non-deleted) documents — hottest query.
        Index(
            "ix_knowledge_documents_tenant_active",
            "tenant_id",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Must match the doc_id stored in ChromaDB chunk metadata.
    doc_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    source_file: Mapped[str] = mapped_column(String(500), nullable=False)
    # SHA-256 of the raw file bytes — used for deduplication.
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        Enum(KnowledgeDocumentStatus, name="knowledge_document_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=KnowledgeDocumentStatus.PENDING,
    )
    # Populated when status = FAILED.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Arbitrary tags from the ingest CLI (e.g. {"topic": "admissions"}).
    tags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ingested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    chunks: Mapped[list["KnowledgeChunkModel"]] = relationship(  # noqa: F821
        back_populates="document",
        lazy="noload",
        cascade="all, delete-orphan",
    )
