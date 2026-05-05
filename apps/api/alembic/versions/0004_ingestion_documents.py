"""Phase 4 — ingestion and document models.

Revision ID: 0004_ingestion_documents
Revises: 0003_business_finance
Create Date: 2026-05-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_ingestion_documents"
down_revision: Union[str, None] = "0003_business_finance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

IMPORT_BATCH_STATUS = sa.Enum("processing", "completed", "failed", name="import_batch_status")
EXTRACTION_STATUS = sa.Enum("pending", "extracted", "needs_review", "approved", "rejected", name="extraction_status")
CANDIDATE_STATUS = sa.Enum("suggested", "approved", "rejected", name="candidate_status")


def upgrade() -> None:
    bind = op.get_bind()
    IMPORT_BATCH_STATUS.create(bind, checkfirst=True)
    EXTRACTION_STATUS.create(bind, checkfirst=True)
    CANDIDATE_STATUS.create(bind, checkfirst=True)

    op.create_table(
        "import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("attachments.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", IMPORT_BATCH_STATUS, nullable=False, server_default=sa.text("'processing'")),
        sa.Column("rows_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rows_imported", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rows_failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.String(length=500)),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_import_batches_tenant_id", "import_batches", ["tenant_id"])
    op.create_index("ix_import_batches_entity_id", "import_batches", ["entity_id"])

    op.create_table(
        "document_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_transactions.id", ondelete="SET NULL")),
        sa.Column("extraction_kind", sa.String(length=32), nullable=False),
        sa.Column("status", EXTRACTION_STATUS, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("extracted_text", sa.String()),
        sa.Column("extracted_data", postgresql.JSONB),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("duplicate_detected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_document_extractions_tenant_id", "document_extractions", ["tenant_id"])
    op.create_index("ix_document_extractions_entity_id", "document_extractions", ["entity_id"])
    op.create_index("ix_document_extractions_attachment_id", "document_extractions", ["attachment_id"])

    op.create_table(
        "extraction_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_extraction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_extractions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_transactions.id", ondelete="SET NULL")),
        sa.Column("suggested_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("suggested_memo", sa.String(length=500)),
        sa.Column("suggested_entry", postgresql.JSONB),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("status", CANDIDATE_STATUS, nullable=False, server_default=sa.text("'suggested'")),
        sa.Column("approved_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id", ondelete="SET NULL")),
        sa.Column("rationale", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_extraction_candidates_tenant_id", "extraction_candidates", ["tenant_id"])
    op.create_index("ix_extraction_candidates_entity_id", "extraction_candidates", ["entity_id"])
    op.create_index("ix_extraction_candidates_document_extraction_id", "extraction_candidates", ["document_extraction_id"])


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("extraction_candidates")
    op.drop_table("document_extractions")
    op.drop_table("import_batches")
    CANDIDATE_STATUS.drop(bind, checkfirst=True)
    EXTRACTION_STATUS.drop(bind, checkfirst=True)
    IMPORT_BATCH_STATUS.drop(bind, checkfirst=True)
