"""Initial schema: tenants, users, sessions, entities, members, accounts, journal, source tx, attachments, audit.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enum types
ENTITY_MODE = sa.Enum("personal", "business", name="entity_mode")
ENTITY_ROLE = sa.Enum("owner", "admin", "accountant", "viewer", "agent", name="entity_role")
ACCOUNT_TYPE = sa.Enum("asset", "liability", "equity", "income", "expense", name="account_type")
ACCOUNT_NORMAL_SIDE = sa.Enum("debit", "credit", name="account_normal_side")
JE_STATUS = sa.Enum("draft", "posted", "voided", name="journal_entry_status")
ST_STATUS = sa.Enum("pending", "matched", "posted", "discarded", name="source_transaction_status")


def upgrade() -> None:
    # pgcrypto and vector are created by infra/docker/postgres/init.sql at first DB init.
    # Create extension here too in case the migration runs against a fresh DB without that init.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # tenants
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # sessions
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("ip", sa.String(length=64)),
        sa.Column("user_agent", sa.String(length=512)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    # entities
    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("mode", ENTITY_MODE, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_entities_tenant_id", "entities", ["tenant_id"])

    # entity_members
    op.create_table(
        "entity_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", ENTITY_ROLE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_id", "user_id", name="uq_entity_members_entity_user"),
    )
    op.create_index("ix_entity_members_entity_id", "entity_members", ["entity_id"])
    op.create_index("ix_entity_members_user_id", "entity_members", ["user_id"])

    # accounts (hierarchical via parent_id)
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="RESTRICT")),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", ACCOUNT_TYPE, nullable=False),
        sa.Column("normal_side", ACCOUNT_NORMAL_SIDE, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_id", "code", name="uq_accounts_entity_code"),
    )
    op.create_index("ix_accounts_entity_id", "accounts", ["entity_id"])
    op.create_index("ix_accounts_parent_id", "accounts", ["parent_id"])

    # source_transactions (created before journal_entries because JE FKs into it)
    op.create_table(
        "source_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("external_ref", sa.String(length=255)),
        sa.Column("occurred_at", sa.DateTime(timezone=True)),
        sa.Column("amount", sa.Numeric(20, 2)),
        sa.Column("currency", sa.String(length=3)),
        sa.Column("merchant", sa.String(length=255)),
        sa.Column("raw", postgresql.JSONB),
        sa.Column("content_hash", sa.String(length=64)),
        sa.Column("status", ST_STATUS, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_source_transactions_entity_id", "source_transactions", ["entity_id"])
    op.create_index("ix_source_transactions_occurred_at", "source_transactions", ["occurred_at"])
    op.create_index("ix_source_transactions_content_hash", "source_transactions", ["content_hash"])

    # journal_entries
    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("memo", sa.String(length=500)),
        sa.Column("reference", sa.String(length=100)),
        sa.Column("status", JE_STATUS, nullable=False, server_default=sa.text("'draft'")),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("posted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("voided_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("voided_reason", sa.String(length=500)),
        sa.Column("voided_by_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id", ondelete="SET NULL")),
        sa.Column("voids_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id", ondelete="SET NULL")),
        sa.Column("linked_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id", ondelete="SET NULL")),
        sa.Column("source_transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_transactions.id", ondelete="SET NULL")),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_journal_entries_entity_id", "journal_entries", ["entity_id"])
    op.create_index("ix_journal_entries_entry_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entries_status", "journal_entries", ["status"])

    # journal_lines
    op.create_table(
        "journal_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("debit", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("credit", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("description", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="ck_journal_lines_single_sided",
        ),
        sa.CheckConstraint("debit >= 0", name="ck_journal_lines_debit_non_negative"),
        sa.CheckConstraint("credit >= 0", name="ck_journal_lines_credit_non_negative"),
    )
    op.create_index("ix_journal_lines_journal_entry_id", "journal_lines", ["journal_entry_id"])
    op.create_index("ix_journal_lines_account_id", "journal_lines", ["account_id"])

    # attachments
    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE")),
        sa.Column("source_transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_transactions.id", ondelete="SET NULL")),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id", ondelete="SET NULL")),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_attachments_tenant_id", "attachments", ["tenant_id"])
    op.create_index("ix_attachments_entity_id", "attachments", ["entity_id"])
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"])

    # audit_logs (append-only at API layer; phase 12 adds DB-level revoke)
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_id", sa.String(length=64)),
        sa.Column("before", postgresql.JSONB),
        sa.Column("after", postgresql.JSONB),
        sa.Column("ip", sa.String(length=64)),
        sa.Column("user_agent", sa.String(length=512)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_object_type", "audit_logs", ["object_type"])
    op.create_index("ix_audit_logs_object_id", "audit_logs", ["object_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("attachments")
    op.drop_table("journal_lines")
    op.drop_table("journal_entries")
    op.drop_table("source_transactions")
    op.drop_table("accounts")
    op.drop_table("entity_members")
    op.drop_table("entities")
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("tenants")

    bind = op.get_bind()
    JE_STATUS.drop(bind, checkfirst=True)
    ST_STATUS.drop(bind, checkfirst=True)
    ACCOUNT_NORMAL_SIDE.drop(bind, checkfirst=True)
    ACCOUNT_TYPE.drop(bind, checkfirst=True)
    ENTITY_ROLE.drop(bind, checkfirst=True)
    ENTITY_MODE.drop(bind, checkfirst=True)
