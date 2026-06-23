"""SQLAlchemy ORM model for the escalations table."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.escalation_trigger import EscalationTrigger
from app.domain.enums.escalation_urgency import EscalationUrgency
from app.infrastructure.database.base import Base


class EscalationModel(Base):
    __tablename__ = "escalations"

    __table_args__ = (
        # Covering index: drives get_open_by_conversation (hottest query).
        Index("ix_escalations_conversation_resolved", "conversation_id", "resolved"),
        # Open, high-urgency escalations across a tenant (agent dashboard).
        Index("ix_escalations_tenant_resolved_urgency", "tenant_id", "resolved", "urgency"),
        Index("ix_escalations_assigned_agent", "assigned_agent_id", "resolved"),
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
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # What caused the escalation (from EscalationRuleEngine).
    trigger: Mapped[str | None] = mapped_column(
        Enum(EscalationTrigger, name="escalation_trigger_type", values_callable=lambda x: [e.value for e in x]), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[str] = mapped_column(
        Enum(EscalationUrgency, name="escalation_urgency", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=EscalationUrgency.NORMAL,
    )
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Staff user currently handling this escalation.
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Legacy string agent identifier — kept for backward compatibility.
    agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    conversation: Mapped["ConversationModel"] = relationship(  # noqa: F821
        back_populates="escalations"
    )
