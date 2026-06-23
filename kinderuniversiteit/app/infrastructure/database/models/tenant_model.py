"""SQLAlchemy ORM model for the tenants table.

Tenants are the top-level multi-tenant isolation boundary.  Every other table
carries an optional tenant_id FK.  In single-tenant deployments the column is
left NULL; in multi-tenant deployments it must be NOT NULL and all queries
must filter on it.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class TenantModel(Base):
    __tablename__ = "tenants"

    __table_args__ = (
        UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # URL-safe identifier used in API paths and subdomain routing.
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Tenant-specific overrides (logo_url, support_email, escalation_email, …).
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Soft delete — rows are never physically removed so FK references stay intact.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
