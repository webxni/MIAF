"""tailscale_settings

Revision ID: 0012_tailscale_settings
Revises: 0011_audit_logs_revoke
Create Date: 2026-05-06
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_tailscale_settings"
down_revision: Union[str, None] = "0011_audit_logs_revoke"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tailscale_settings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tailscale_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tailscale_mode", sa.String(32), nullable=False, server_default="off"),
        sa.Column("tailscale_target_url", sa.String(200), nullable=False, server_default="http://127.0.0.1:80"),
        sa.Column("tailscale_hostname", sa.String(253), nullable=True),
        sa.Column("tailscale_tailnet_url", sa.String(500), nullable=True),
        sa.Column("tailscale_last_status", sa.Text(), nullable=True),
        sa.Column("tailscale_last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tailscale_setup_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tailscale_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_tailscale_settings_tenant_id_tenants", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_tailscale_settings"),
        sa.UniqueConstraint("tenant_id", name="uq_tailscale_settings_tenant_id"),
    )
    op.create_index("ix_tailscale_settings_tenant_id", "tailscale_settings", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_tailscale_settings_tenant_id", table_name="tailscale_settings")
    op.drop_table("tailscale_settings")
