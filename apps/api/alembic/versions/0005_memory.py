"""Phase 7 — financial memory.

Revision ID: 0005_memory
Revises: 0004_ingestion_documents
Create Date: 2026-05-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_memory"
down_revision: Union[str, None] = "0004_ingestion_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MEMORY_TYPE = sa.Enum(
    "user_profile",
    "personal_preference",
    "business_profile",
    "financial_rule",
    "merchant_rule",
    "tax_context",
    "goal_context",
    "risk_preference",
    "recurring_pattern",
    "advisor_note",
    name="memory_type",
)
MEMORY_REVIEW_STATUS = sa.Enum("accepted", "needs_update", "archived", name="memory_review_status")
MEMORY_EVENT_TYPE = sa.Enum("created", "updated", "accessed", "deleted", "expired", "reviewed", "promoted", name="memory_event_type")


def upgrade() -> None:
    bind = op.get_bind()
    MEMORY_TYPE.create(bind, checkfirst=True)
    MEMORY_REVIEW_STATUS.create(bind, checkfirst=True)
    MEMORY_EVENT_TYPE.create(bind, checkfirst=True)

    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE")),
        sa.Column("memory_type", MEMORY_TYPE, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(length=500)),
        sa.Column("keywords", postgresql.JSONB),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'user'")),
        sa.Column("consent_granted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_memories_tenant_id", "memories", ["tenant_id"])
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_index("ix_memories_entity_id", "memories", ["entity_id"])
    op.create_index("ix_memories_memory_type", "memories", ["memory_type"])

    op.create_table(
        "memory_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=False, server_default=sa.text("'deterministic-v1'")),
        sa.Column("embedding", postgresql.JSONB, nullable=False),
        sa.Column("redacted_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_memory_embeddings_tenant_id", "memory_embeddings", ["tenant_id"])
    op.create_index("ix_memory_embeddings_memory_id", "memory_embeddings", ["memory_id"])

    op.create_table(
        "memory_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event_type", MEMORY_EVENT_TYPE, nullable=False),
        sa.Column("payload", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_memory_events_tenant_id", "memory_events", ["tenant_id"])
    op.create_index("ix_memory_events_memory_id", "memory_events", ["memory_id"])
    op.create_index("ix_memory_events_event_type", "memory_events", ["event_type"])

    op.create_table(
        "memory_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", MEMORY_REVIEW_STATUS, nullable=False),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_memory_reviews_tenant_id", "memory_reviews", ["tenant_id"])
    op.create_index("ix_memory_reviews_memory_id", "memory_reviews", ["memory_id"])


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("memory_reviews")
    op.drop_table("memory_events")
    op.drop_table("memory_embeddings")
    op.drop_table("memories")
    MEMORY_EVENT_TYPE.drop(bind, checkfirst=True)
    MEMORY_REVIEW_STATUS.drop(bind, checkfirst=True)
    MEMORY_TYPE.drop(bind, checkfirst=True)
