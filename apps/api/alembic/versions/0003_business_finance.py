"""Phase 3 — business finance models and reports.

Revision ID: 0003_business_finance
Revises: 0002_personal_finance
Create Date: 2026-05-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_business_finance"
down_revision: Union[str, None] = "0002_personal_finance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BUSINESS_DOCUMENT_STATUS = sa.Enum("draft", "posted", "partial", "paid", "voided", name="business_document_status")
PAYMENT_KIND = sa.Enum("customer_receipt", "vendor_payment", name="payment_kind")
CLOSING_PERIOD_STATUS = sa.Enum("open", "soft_closed", "closed", name="closing_period_status")


def upgrade() -> None:
    BUSINESS_DOCUMENT_STATUS.create(op.get_bind(), checkfirst=True)
    PAYMENT_KIND.create(op.get_bind(), checkfirst=True)
    CLOSING_PERIOD_STATUS.create(op.get_bind(), checkfirst=True)

    op.create_table("customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=255)),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_id", "name", name="uq_customers_entity_name"),
    )
    op.create_index("ix_customers_entity_id", "customers", ["entity_id"])

    op.create_table("vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=255)),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_id", "name", name="uq_vendors_entity_name"),
    )
    op.create_index("ix_vendors_entity_id", "vendors", ["entity_id"])

    op.create_table("invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("number", sa.String(length=64), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("memo", sa.String(length=500)),
        sa.Column("subtotal", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("balance_due", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("status", BUSINESS_DOCUMENT_STATUS, nullable=False, server_default=sa.text("'draft'")),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("posted_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_id", "number", name="uq_invoices_entity_number"),
    )
    op.create_index("ix_invoices_entity_id", "invoices", ["entity_id"])
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])

    op.create_table("invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_price", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("revenue_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])
    op.create_index("ix_invoice_lines_revenue_account_id", "invoice_lines", ["revenue_account_id"])

    op.create_table("bills",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("number", sa.String(length=64), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("memo", sa.String(length=500)),
        sa.Column("subtotal", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("balance_due", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("status", BUSINESS_DOCUMENT_STATUS, nullable=False, server_default=sa.text("'draft'")),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("posted_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_id", "number", name="uq_bills_entity_number"),
    )
    op.create_index("ix_bills_entity_id", "bills", ["entity_id"])
    op.create_index("ix_bills_vendor_id", "bills", ["vendor_id"])

    op.create_table("bill_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_price", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("expense_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_bill_lines_bill_id", "bill_lines", ["bill_id"])
    op.create_index("ix_bill_lines_expense_account_id", "bill_lines", ["expense_account_id"])

    op.create_table("payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", PAYMENT_KIND, nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("reference", sa.String(length=100)),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL")),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bills.id", ondelete="SET NULL")),
        sa.Column("posted_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_payments_entity_id", "payments", ["entity_id"])

    op.create_table("tax_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("jurisdiction", sa.String(length=200)),
        sa.Column("rate", sa.Numeric(7, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_id", "name", name="uq_tax_rates_entity_name"),
    )
    op.create_index("ix_tax_rates_entity_id", "tax_rates", ["entity_id"])

    op.create_table("tax_reserves",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("estimated_tax", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("reserved_amount", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tax_reserves_entity_id", "tax_reserves", ["entity_id"])

    op.create_table("closing_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", CLOSING_PERIOD_STATUS, nullable=False, server_default=sa.text("'open'")),
        sa.Column("notes", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_id", "period_start", "period_end", name="uq_closing_periods_entity_period"),
    )
    op.create_index("ix_closing_periods_entity_id", "closing_periods", ["entity_id"])


def downgrade() -> None:
    op.drop_table("closing_periods")
    op.drop_table("tax_reserves")
    op.drop_table("tax_rates")
    op.drop_table("payments")
    op.drop_table("bill_lines")
    op.drop_table("bills")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    op.drop_table("vendors")
    op.drop_table("customers")
    CLOSING_PERIOD_STATUS.drop(op.get_bind(), checkfirst=True)
    PAYMENT_KIND.drop(op.get_bind(), checkfirst=True)
    BUSINESS_DOCUMENT_STATUS.drop(op.get_bind(), checkfirst=True)
