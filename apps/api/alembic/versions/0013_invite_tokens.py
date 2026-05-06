"""invite_tokens

Revision ID: 0013_invite_tokens
Revises: 0012_tailscale_settings
Create Date: 2026-05-06
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_invite_tokens"
down_revision: Union[str, None] = "0012_tailscale_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inviter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("token", sa.String(96), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_invite_tokens_tenant_id_tenants", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], name="fk_invite_tokens_inviter_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_invite_tokens"),
        sa.UniqueConstraint("token", name="uq_invite_tokens_token"),
    )
    op.create_index("ix_invite_tokens_tenant_id", "invite_tokens", ["tenant_id"])
    op.create_index("ix_invite_tokens_email", "invite_tokens", ["email"])
    op.create_index("ix_invite_tokens_token", "invite_tokens", ["token"])


def downgrade() -> None:
    op.drop_table("invite_tokens")
