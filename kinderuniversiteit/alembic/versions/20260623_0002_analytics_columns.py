"""Add analytics columns: response_time_ms, is_fallback; relax conversation_id nullability.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-23
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make conversation_id nullable so fallback events (fired before a
    # conversation row exists) can still be recorded.
    op.alter_column(
        "analytics_events",
        "conversation_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True)
        if hasattr(sa.dialects, "postgresql")
        else sa.UUID(),
        nullable=True,
    )

    # Wall-clock pipeline duration for average-response-time reporting.
    op.add_column(
        "analytics_events",
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
    )

    # Distinguishes AI-failure fallback events from normal message events.
    op.add_column(
        "analytics_events",
        sa.Column(
            "is_fallback",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Compound indexes that drive the two hot reporting query patterns.
    op.create_index(
        "ix_analytics_events_created_event_type",
        "analytics_events",
        ["created_at", "event_type"],
    )
    op.create_index(
        "ix_analytics_events_created_channel",
        "analytics_events",
        ["created_at", "channel"],
    )


def downgrade() -> None:
    op.drop_index("ix_analytics_events_created_channel", table_name="analytics_events")
    op.drop_index("ix_analytics_events_created_event_type", table_name="analytics_events")
    op.drop_column("analytics_events", "is_fallback")
    op.drop_column("analytics_events", "response_time_ms")

    # Restore NOT NULL — will fail if any NULL rows were inserted.
    op.alter_column(
        "analytics_events",
        "conversation_id",
        nullable=False,
    )
