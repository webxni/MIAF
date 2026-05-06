"""Phase 12 — user settings.

Revision ID: 0010_user_settings
Revises: 0009_login_attempts
Create Date: 2026-05-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_user_settings"
down_revision: Union[str, None] = "0009_login_attempts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jurisdiction", sa.String(length=64)),
        sa.Column("base_currency", sa.String(length=3), nullable=True, server_default=sa.text("'USD'")),
        sa.Column("fiscal_year_start_month", sa.Integer(), nullable=True, server_default=sa.text("1")),
        sa.Column("ai_provider", sa.String(length=32)),
        sa.Column("ai_model", sa.String(length=64)),
        sa.Column("ai_api_key_encrypted", sa.LargeBinary()),
        sa.Column("ai_api_key_hint", sa.String(length=8)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "fiscal_year_start_month IS NULL OR fiscal_year_start_month BETWEEN 1 AND 12",
            name="ck_user_settings_fiscal_year_start_month_range",
        ),
    )
    op.create_index("ix_user_settings_tenant_id", "user_settings", ["tenant_id"])
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_table("user_settings")
