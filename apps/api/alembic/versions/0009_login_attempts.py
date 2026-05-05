"""Phase 12 — login attempt tracking.

Revision ID: 0009_login_attempts
Revises: 0008_telegram
Create Date: 2026-05-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_login_attempts"
down_revision: Union[str, None] = "0008_telegram"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="SET NULL")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("ip", sa.String(length=64)),
        sa.Column("user_agent", sa.String(length=512)),
        sa.Column("was_successful", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("failure_reason", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_login_attempts_tenant_id", "login_attempts", ["tenant_id"])
    op.create_index("ix_login_attempts_user_id", "login_attempts", ["user_id"])
    op.create_index("ix_login_attempts_email", "login_attempts", ["email"])
    op.create_index("ix_login_attempts_ip", "login_attempts", ["ip"])
    op.create_index("ix_login_attempts_was_successful", "login_attempts", ["was_successful"])
    op.create_index("ix_login_attempts_failure_reason", "login_attempts", ["failure_reason"])


def downgrade() -> None:
    op.drop_table("login_attempts")
