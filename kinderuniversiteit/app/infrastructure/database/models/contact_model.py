"""SQLAlchemy ORM model for the contacts table."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums.channel import Channel
from app.infrastructure.database.base import Base


class ContactModel(Base):
    __tablename__ = "contacts"

    __table_args__ = (
        # Single-tenant / legacy: one external_id per channel globally.
        UniqueConstraint("external_id", "channel", name="uq_contacts_external_channel"),
        Index("ix_contacts_tenant_id", "tenant_id"),
        # Multi-tenant covering index: drives get_by_external_id queries.
        Index("ix_contacts_tenant_external_channel", "tenant_id", "external_id", "channel"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # NULL in single-tenant mode; required in multi-tenant deployments.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(Enum(Channel, name="channel", values_callable=lambda x: [e.value for e in x]), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="nl")
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
