"""SQLAlchemy ORM model for the api_logs table.

One row per inbound HTTP request.  High write volume — consider range
partitioning on created_at in production (e.g. monthly partitions via
pg_partman) and a short retention TTL (30–90 days).

The request_id UUID is the same correlation ID that structlog binds at the
start of each webhook handler so log lines can be joined to this table.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class APILogModel(Base):
    __tablename__ = "api_logs"

    __table_args__ = (
        UniqueConstraint("request_id", name="uq_api_logs_request_id"),
        Index("ix_api_logs_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_api_logs_tenant_path_created_at", "tenant_id", "path", "created_at"),
        Index("ix_api_logs_tenant_status_created_at", "tenant_id", "status_code", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        # No FK — tenant may not exist for unauthenticated requests.
        nullable=True,
        index=True,
    )
    # Structlog request_id bound at the top of the webhook handler.
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    request_body_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Populated for webhook requests; NULL for health checks / admin API calls.
    contact_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Populated on error responses.
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
