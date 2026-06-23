"""SQLAlchemy ORM model for the audit_logs table.

Append-only record of all significant state changes — escalation resolution,
document deletion, user role changes, conversation closure, etc.

Rows are never updated or deleted.  Retention policy is enforced at the DB
level (e.g. pg_partman TTL on the created_at partition key in production).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("ix_audit_logs_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_audit_logs_tenant_action", "tenant_id", "action"),
        Index("ix_audit_logs_resource", "tenant_id", "resource_type", "resource_id"),
        Index("ix_audit_logs_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # NULL for system-generated events (scheduled jobs, automated escalations).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Dot-namespaced action string: "{resource}.{verb}"
    # Examples: "escalation.resolved", "document.deleted", "user.role_changed"
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    # Full before/after snapshots for diffing in the admin UI.
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Supports both IPv4 (15 chars) and IPv6 (39 chars).
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
