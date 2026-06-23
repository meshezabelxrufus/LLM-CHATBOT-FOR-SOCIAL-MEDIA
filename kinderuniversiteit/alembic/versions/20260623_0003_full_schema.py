"""Full schema expansion: multi-tenant support, users, knowledge base, daily metrics,
audit logs, API logs, escalation enhancements.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-23

What this migration does
────────────────────────
Phase 1 – Extend existing enum types
  • conversation_state  ← add 'resolved'
  (Must execute before the transaction closes; value is usable in subsequent
  migrations once this one commits.)

Phase 2 – Create new enum types
  • user_role                    admin | agent | viewer
  • tenant_plan                  free | starter | professional | enterprise
  • knowledge_document_status    pending | processing | ready | failed
  • escalation_trigger_type      payment_status | financial_request | ai_signal | low_confidence
  • escalation_urgency           high | normal | low

Phase 3 – Create new tables (in dependency order)
  tenants → users → knowledge_documents → knowledge_chunks
  daily_metrics → audit_logs → api_logs

Phase 4 – Add columns to existing tables
  contacts       ← tenant_id
  conversations  ← tenant_id, assigned_agent_id, closed_at
  messages       ← tenant_id
  escalations    ← tenant_id, trigger, urgency, assigned_agent_id
  analytics_events ← tenant_id

Phase 5 – Add new indexes

Multi-tenant notes
──────────────────
All tenant_id FKs are nullable so existing single-tenant data is unaffected.
To enforce multi-tenancy: backfill tenant_id for all rows, then add
NOT NULL constraints in a subsequent migration.

The daily_metrics functional unique index uses COALESCE to handle NULL channel
(which represents the cross-channel total row) correctly, since standard
UNIQUE constraints treat every NULL as distinct.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── Phase 1: Extend existing enum types ───────────────────────────────────
    # ALTER TYPE … ADD VALUE cannot run inside a transaction in PostgreSQL < 12.
    # PostgreSQL 12+ allows it as long as the new value is not used in the
    # same transaction.  We rely on the autocommit mode Alembic uses here.
    conn.execute(
        sa.text("ALTER TYPE conversation_state ADD VALUE IF NOT EXISTS 'resolved'")
    )

    # ── Phase 2: New enum types ───────────────────────────────────────────────

    for name, values in [
        ("user_role", ["admin", "agent", "viewer"]),
        ("tenant_plan", ["free", "starter", "professional", "enterprise"]),
        (
            "knowledge_document_status",
            ["pending", "processing", "ready", "failed"],
        ),
        (
            "escalation_trigger_type",
            ["payment_status", "financial_request", "ai_signal", "low_confidence"],
        ),
        ("escalation_urgency", ["high", "normal", "low"]),
    ]:
        postgresql.ENUM(*values, name=name, create_type=True).create(
            conn, checkfirst=True
        )

    # ── Phase 3: New tables ───────────────────────────────────────────────────

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
        sa.Column(
            "role",
            postgresql.ENUM(name="user_role", create_type=False),
            nullable=False,
            server_default="agent",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("doc_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("source_file", sa.String(500), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "status",
            postgresql.ENUM(name="knowledge_document_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "ingested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("doc_id", name="uq_knowledge_documents_doc_id"),
    )
    op.create_index("ix_knowledge_documents_tenant_id", "knowledge_documents", ["tenant_id"])
    op.create_index("ix_knowledge_documents_file_hash", "knowledge_documents", ["file_hash"])
    op.create_index(
        "ix_knowledge_documents_tenant_status",
        "knowledge_documents",
        ["tenant_id", "status"],
    )
    # Partial index — active documents only (hottest query path for the AI pipeline).
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_tenant_active "
            "ON knowledge_documents (tenant_id) WHERE deleted_at IS NULL"
        )
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_id", sa.String(500), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content_preview", sa.String(500), nullable=False, server_default=""),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("chunk_id", name="uq_knowledge_chunks_chunk_id"),
        sa.UniqueConstraint(
            "document_id", "page_number", "chunk_index",
            name="uq_knowledge_chunks_position",
        ),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_tenant_id", "knowledge_chunks", ["tenant_id"])

    op.create_table(
        "daily_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("conversation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("new_conversation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("escalation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fallback_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_response_time_ms", sa.Float, nullable=True),
        sa.Column("avg_confidence_score", sa.Float, nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_daily_metrics_tenant_id", "daily_metrics", ["tenant_id"])
    op.create_index("ix_daily_metrics_date", "daily_metrics", ["date"])
    # Functional unique index — COALESCE handles NULL channel (= all-channels row).
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_daily_metrics_tenant_date_channel "
            "ON daily_metrics (COALESCE(tenant_id::text, ''), date, COALESCE(channel, ''))"
        )
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_tenant_created_at", "audit_logs", ["tenant_id", "created_at"])
    op.create_index("ix_audit_logs_tenant_action", "audit_logs", ["tenant_id", "action"])
    op.create_index(
        "ix_audit_logs_resource",
        "audit_logs",
        ["tenant_id", "resource_type", "resource_id"],
    )
    op.create_index("ix_audit_logs_user_created_at", "audit_logs", ["user_id", "created_at"])

    op.create_table(
        "api_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("request_body_size_bytes", sa.Integer, nullable=True),
        sa.Column("response_body_size_bytes", sa.Integer, nullable=True),
        sa.Column("response_time_ms", sa.Integer, nullable=True),
        sa.Column("contact_id", sa.String(255), nullable=True),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("request_id", name="uq_api_logs_request_id"),
    )
    op.create_index("ix_api_logs_tenant_created_at", "api_logs", ["tenant_id", "created_at"])
    op.create_index(
        "ix_api_logs_tenant_path_created_at",
        "api_logs",
        ["tenant_id", "path", "created_at"],
    )
    op.create_index(
        "ix_api_logs_tenant_status_created_at",
        "api_logs",
        ["tenant_id", "status_code", "created_at"],
    )

    # ── Phase 4: Modify existing tables ──────────────────────────────────────

    # contacts
    op.add_column(
        "contacts",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # conversations
    op.add_column(
        "conversations",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "assigned_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "conversations",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # messages
    op.add_column(
        "messages",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # escalations
    op.add_column(
        "escalations",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "escalations",
        sa.Column("trigger", postgresql.ENUM(name="escalation_trigger_type", create_type=False), nullable=True),
    )
    op.add_column(
        "escalations",
        sa.Column(
            "urgency",
            postgresql.ENUM(name="escalation_urgency", create_type=False),
            nullable=False,
            server_default="normal",
        ),
    )
    op.add_column(
        "escalations",
        sa.Column(
            "assigned_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # analytics_events
    op.add_column(
        "analytics_events",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # ── Phase 5: New indexes on existing tables ───────────────────────────────

    op.create_index("ix_contacts_tenant_id", "contacts", ["tenant_id"])
    op.create_index(
        "ix_contacts_tenant_external_channel",
        "contacts",
        ["tenant_id", "external_id", "channel"],
    )
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    op.create_index(
        "ix_conversations_tenant_contact_channel_state",
        "conversations",
        ["tenant_id", "contact_id", "channel", "state"],
    )
    op.create_index(
        "ix_conversations_tenant_last_interaction",
        "conversations",
        ["tenant_id", "last_interaction_at"],
    )
    op.create_index(
        "ix_conversations_assigned_agent",
        "conversations",
        ["assigned_agent_id", "state"],
    )
    op.create_index("ix_messages_tenant_created_at", "messages", ["tenant_id", "created_at"])
    op.create_index("ix_escalations_tenant_id", "escalations", ["tenant_id"])
    op.create_index(
        "ix_escalations_tenant_resolved_urgency",
        "escalations",
        ["tenant_id", "resolved", "urgency"],
    )
    op.create_index(
        "ix_escalations_assigned_agent",
        "escalations",
        ["assigned_agent_id", "resolved"],
    )
    op.create_index(
        "ix_analytics_events_tenant_created_at",
        "analytics_events",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    # ── Remove indexes on existing tables ─────────────────────────────────────
    for idx in [
        ("analytics_events", "ix_analytics_events_tenant_created_at"),
        ("escalations", "ix_escalations_assigned_agent"),
        ("escalations", "ix_escalations_tenant_resolved_urgency"),
        ("escalations", "ix_escalations_tenant_id"),
        ("messages", "ix_messages_tenant_created_at"),
        ("conversations", "ix_conversations_assigned_agent"),
        ("conversations", "ix_conversations_tenant_last_interaction"),
        ("conversations", "ix_conversations_tenant_contact_channel_state"),
        ("conversations", "ix_conversations_tenant_id"),
        ("contacts", "ix_contacts_tenant_external_channel"),
        ("contacts", "ix_contacts_tenant_id"),
    ]:
        op.drop_index(idx[1], table_name=idx[0])

    # ── Remove columns from existing tables ───────────────────────────────────
    op.drop_column("analytics_events", "tenant_id")
    op.drop_column("escalations", "assigned_agent_id")
    op.drop_column("escalations", "urgency")
    op.drop_column("escalations", "trigger")
    op.drop_column("escalations", "tenant_id")
    op.drop_column("messages", "tenant_id")
    op.drop_column("conversations", "closed_at")
    op.drop_column("conversations", "assigned_agent_id")
    op.drop_column("conversations", "tenant_id")
    op.drop_column("contacts", "tenant_id")

    # ── Drop new tables (in reverse FK dependency order) ──────────────────────
    op.drop_table("api_logs")
    op.drop_table("audit_logs")
    op.drop_table("daily_metrics")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("users")
    op.drop_table("tenants")

    # ── Drop new enum types ───────────────────────────────────────────────────
    for name in [
        "escalation_urgency",
        "escalation_trigger_type",
        "knowledge_document_status",
        "tenant_plan",
        "user_role",
    ]:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {name}"))

    # Note: removing 'resolved' from conversation_state is not supported by
    # PostgreSQL without dropping and recreating the type.  The downgrade
    # leaves conversation_state with the extra value, which is harmless.
