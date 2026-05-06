"""Phase 10 — telegram integration.

Revision ID: 0008_telegram
Revises: 0007_skills_engine
Create Date: 2026-05-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_telegram"
down_revision: Union[str, None] = "0007_skills_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Pass create_type=False on the column-bound types so SQLAlchemy doesn't
    # also emit CREATE TYPE when the columns are added below — the explicit
    # postgresql.ENUM(...).create(checkfirst=True) calls own creation.
    entity_mode = postgresql.ENUM("personal", "business", name="telegram_active_mode", create_type=False)
    direction = postgresql.ENUM("inbound", "outbound", name="telegram_message_direction", create_type=False)
    message_type = postgresql.ENUM("text", "image", "pdf", "voice", "command", "system", name="telegram_message_type", create_type=False)
    message_status = postgresql.ENUM("processed", "rejected", "rate_limited", name="telegram_message_status", create_type=False)
    postgresql.ENUM("personal", "business", name="telegram_active_mode").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("inbound", "outbound", name="telegram_message_direction").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("text", "image", "pdf", "voice", "command", "system", name="telegram_message_type").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("processed", "rejected", "rate_limited", name="telegram_message_status").create(op.get_bind(), checkfirst=True)

    op.create_table(
        "telegram_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("personal_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="SET NULL")),
        sa.Column("business_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="SET NULL")),
        sa.Column("active_mode", entity_mode, nullable=False, server_default=sa.text("'personal'")),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=False),
        sa.Column("telegram_username", sa.String(length=100)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("telegram_user_id", name="uq_telegram_links_telegram_user_id"),
    )
    op.create_index("ix_telegram_links_tenant_id", "telegram_links", ["tenant_id"])
    op.create_index("ix_telegram_links_user_id", "telegram_links", ["user_id"])
    op.create_index("ix_telegram_links_personal_entity_id", "telegram_links", ["personal_entity_id"])
    op.create_index("ix_telegram_links_business_entity_id", "telegram_links", ["business_entity_id"])

    op.create_table(
        "telegram_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="SET NULL")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="SET NULL")),
        sa.Column("link_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("telegram_links.id", ondelete="SET NULL")),
        sa.Column("direction", direction, nullable=False),
        sa.Column("message_type", message_type, nullable=False),
        sa.Column("status", message_status, nullable=False, server_default=sa.text("'processed'")),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=False),
        sa.Column("telegram_message_id", sa.String(length=64)),
        sa.Column("text_body", sa.Text()),
        sa.Column("file_name", sa.String(length=255)),
        sa.Column("file_mime_type", sa.String(length=120)),
        sa.Column("payload", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_telegram_messages_tenant_id", "telegram_messages", ["tenant_id"])
    op.create_index("ix_telegram_messages_user_id", "telegram_messages", ["user_id"])
    op.create_index("ix_telegram_messages_entity_id", "telegram_messages", ["entity_id"])
    op.create_index("ix_telegram_messages_link_id", "telegram_messages", ["link_id"])
    op.create_index("ix_telegram_messages_direction", "telegram_messages", ["direction"])
    op.create_index("ix_telegram_messages_message_type", "telegram_messages", ["message_type"])
    op.create_index("ix_telegram_messages_status", "telegram_messages", ["status"])
    op.create_index("ix_telegram_messages_telegram_user_id", "telegram_messages", ["telegram_user_id"])
    op.create_index("ix_telegram_messages_telegram_chat_id", "telegram_messages", ["telegram_chat_id"])
    op.create_index("ix_telegram_messages_telegram_message_id", "telegram_messages", ["telegram_message_id"])


def downgrade() -> None:
    op.drop_table("telegram_messages")
    op.drop_table("telegram_links")
    postgresql.ENUM(name="telegram_message_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="telegram_message_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="telegram_message_direction").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="telegram_active_mode").drop(op.get_bind(), checkfirst=True)
