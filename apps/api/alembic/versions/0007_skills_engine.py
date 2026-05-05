"""Phase 9 — skills engine persistence.

Revision ID: 0007_skills_engine
Revises: 0006_heartbeat_ops
Create Date: 2026-05-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_skills_engine"
down_revision: Union[str, None] = "0006_heartbeat_ops"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skill_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("installed_version", sa.String(length=32), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "skill_name", name="uq_skill_states_tenant_skill"),
    )
    op.create_index("ix_skill_states_tenant_id", "skill_states", ["tenant_id"])
    op.create_index("ix_skill_states_skill_name", "skill_states", ["skill_name"])

    op.create_table(
        "skill_run_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="SET NULL")),
        sa.Column("skill_name", sa.String(length=100), nullable=False),
        sa.Column("skill_version", sa.String(length=32), nullable=False),
        sa.Column("permissions", postgresql.JSONB, nullable=False),
        sa.Column("input_payload", postgresql.JSONB),
        sa.Column("output_payload", postgresql.JSONB),
        sa.Column("result_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_skill_run_logs_tenant_id", "skill_run_logs", ["tenant_id"])
    op.create_index("ix_skill_run_logs_user_id", "skill_run_logs", ["user_id"])
    op.create_index("ix_skill_run_logs_entity_id", "skill_run_logs", ["entity_id"])
    op.create_index("ix_skill_run_logs_skill_name", "skill_run_logs", ["skill_name"])
    op.create_index("ix_skill_run_logs_result_status", "skill_run_logs", ["result_status"])


def downgrade() -> None:
    op.drop_table("skill_run_logs")
    op.drop_table("skill_states")
