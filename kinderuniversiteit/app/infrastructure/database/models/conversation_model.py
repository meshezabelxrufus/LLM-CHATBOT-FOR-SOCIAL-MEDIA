"""SQLAlchemy ORM model for the conversations table."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.channel import Channel
from app.domain.enums.conversation_state import ConversationState
from app.infrastructure.database.base import Base


class ConversationModel(Base):
    __tablename__ = "conversations"

    __table_args__ = (
        # Hot path: find the active session for a contact on a specific channel.
        Index(
            "ix_conversations_contact_channel_state",
            "contact_id", "channel", "state",
        ),
        # Multi-tenant variant of the same query.
        Index(
            "ix_conversations_tenant_contact_channel_state",
            "tenant_id", "contact_id", "channel", "state",
        ),
        # Recency queries (idle-session cleanup, last-active dashboards).
        Index("ix_conversations_tenant_last_interaction", "tenant_id", "last_interaction_at"),
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
    contact_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(Enum(Channel, name="channel", values_callable=lambda x: [e.value for e in x]), nullable=False)
    state: Mapped[str] = mapped_column(
        Enum(ConversationState, name="conversation_state", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ConversationState.ACTIVE,
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="nl")
    # Staff member currently handling this conversation (set on escalation assignment).
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_interaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when state transitions to CLOSED or RESOLVED.
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    messages: Mapped[list["MessageModel"]] = relationship(  # noqa: F821
        back_populates="conversation",
        lazy="noload",
        order_by="MessageModel.created_at",
    )
    escalations: Mapped[list["EscalationModel"]] = relationship(  # noqa: F821
        back_populates="conversation",
        lazy="noload",
        order_by="EscalationModel.created_at",
    )
