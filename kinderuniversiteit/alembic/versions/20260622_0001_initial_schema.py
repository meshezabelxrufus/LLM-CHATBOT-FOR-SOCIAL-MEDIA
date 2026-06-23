"""Initial schema — contacts, conversations, messages, escalations, analytics_events.

Revision ID: 0001
Revises:
Create Date: 2026-06-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── PostgreSQL enum types ─────────────────────────────────────────────────
    # Create enum types before the tables that reference them so that Alembic
    # can apply this migration cleanly even on a fresh database.

    channel_enum = postgresql.ENUM(
        "facebook", "instagram", "whatsapp",
        name="channel",
        create_type=True,
    )
    conversation_state_enum = postgresql.ENUM(
        "active", "escalated", "closed",
        name="conversation_state",
        create_type=True,
    )
    message_role_enum = postgresql.ENUM(
        "user", "assistant", "system",
        name="message_role",
        create_type=True,
    )

    channel_enum.create(op.get_bind(), checkfirst=True)
    conversation_state_enum.create(op.get_bind(), checkfirst=True)
    message_role_enum.create(op.get_bind(), checkfirst=True)

    # ── contacts ──────────────────────────────────────────────────────────────
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("channel", postgresql.ENUM(name="channel", create_type=False), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("locale", sa.String(10), nullable=False, server_default="nl"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "external_id", "channel", name="uq_contacts_external_channel"
        ),
    )
    op.create_index(
        "ix_contacts_external_id", "contacts", ["external_id"]
    )

    # ── conversations ─────────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contact_id", sa.String(255), nullable=False),
        sa.Column("channel", postgresql.ENUM(name="channel", create_type=False), nullable=False),
        sa.Column(
            "state",
            postgresql.ENUM(name="conversation_state", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("language", sa.String(10), nullable=False, server_default="nl"),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_conversations_contact_id", "conversations", ["contact_id"])
    # Compound index: drives get_active_by_contact — the hottest query path.
    op.create_index(
        "ix_conversations_contact_channel_state",
        "conversations",
        ["contact_id", "channel", "state"],
    )

    # ── messages ──────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", postgresql.ENUM(name="message_role", create_type=False), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    # Covering index for history queries: all messages for a conversation in order.
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at"],
    )

    # ── escalations ───────────────────────────────────────────────────────────
    op.create_table(
        "escalations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("agent_id", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_escalations_conversation_id", "escalations", ["conversation_id"]
    )
    # Covering index: drives get_open_by_conversation.
    op.create_index(
        "ix_escalations_conversation_resolved",
        "escalations",
        ["conversation_id", "resolved"],
    )

    # ── analytics_events ──────────────────────────────────────────────────────
    op.create_table(
        "analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("escalated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "payload",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_analytics_events_conversation_id",
        "analytics_events",
        ["conversation_id"],
    )
    op.create_index(
        "ix_analytics_events_event_type", "analytics_events", ["event_type"]
    )


def downgrade() -> None:
    op.drop_table("analytics_events")
    op.drop_table("escalations")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("contacts")

    op.execute("DROP TYPE IF EXISTS message_role")
    op.execute("DROP TYPE IF EXISTS conversation_state")
    op.execute("DROP TYPE IF EXISTS channel")
