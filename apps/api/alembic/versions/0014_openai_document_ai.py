"""openai_document_ai

Revision ID: 0014_openai_document_ai
Revises: 0013_invite_tokens
Create Date: 2026-05-07
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_openai_document_ai"
down_revision: Union[str, None] = "0013_invite_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("openai_document_ai_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "user_settings",
        sa.Column("openai_document_ai_consent_granted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("user_settings", sa.Column("openai_vision_model", sa.String(length=64), nullable=True))
    op.add_column("user_settings", sa.Column("openai_pdf_model", sa.String(length=64), nullable=True))
    op.add_column(
        "user_settings", sa.Column("openai_transcription_model", sa.String(length=64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_settings", "openai_transcription_model")
    op.drop_column("user_settings", "openai_pdf_model")
    op.drop_column("user_settings", "openai_vision_model")
    op.drop_column("user_settings", "openai_document_ai_consent_granted")
    op.drop_column("user_settings", "openai_document_ai_enabled")
