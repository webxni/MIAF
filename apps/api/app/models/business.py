from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPK

MONEY = Numeric(20, 2)
QTY = Numeric(20, 4)


class BusinessDocumentStatus(str, enum.Enum):
    draft = "draft"
    posted = "posted"
    partial = "partial"
    paid = "paid"
    voided = "voided"


class PaymentKind(str, enum.Enum):
    customer_receipt = "customer_receipt"
    vendor_payment = "vendor_payment"


class ClosingPeriodStatus(str, enum.Enum):
    open = "open"
    soft_closed = "soft_closed"
    closed = "closed"


class Customer(UUIDPK, Timestamps, Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("entity_id", "name", name="uq_customers_entity_name"),)

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Vendor(UUIDPK, Timestamps, Base):
    __tablename__ = "vendors"
    __table_args__ = (UniqueConstraint("entity_id", "name", name="uq_vendors_entity_name"),)

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Invoice(UUIDPK, Timestamps, Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("entity_id", "number", name="uq_invoices_entity_number"),)

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(64), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    memo: Mapped[str | None] = mapped_column(String(500))
    subtotal: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    balance_due: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    status: Mapped[BusinessDocumentStatus] = mapped_column(
        SAEnum(BusinessDocumentStatus, name="business_document_status"),
        nullable=False,
        default=BusinessDocumentStatus.draft,
        index=True,
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL")
    )

    lines: Mapped[list[InvoiceLine]] = relationship(
        "InvoiceLine", back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLine.line_no"
    )


class InvoiceLine(UUIDPK, Timestamps, Base):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    revenue_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="lines")


class Bill(UUIDPK, Timestamps, Base):
    __tablename__ = "bills"
    __table_args__ = (UniqueConstraint("entity_id", "number", name="uq_bills_entity_number"),)

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(64), nullable=False)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    memo: Mapped[str | None] = mapped_column(String(500))
    subtotal: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    balance_due: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    status: Mapped[BusinessDocumentStatus] = mapped_column(
        SAEnum(BusinessDocumentStatus, name="business_document_status", create_type=False),
        nullable=False,
        default=BusinessDocumentStatus.draft,
        index=True,
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL")
    )

    lines: Mapped[list[BillLine]] = relationship(
        "BillLine", back_populates="bill", cascade="all, delete-orphan", order_by="BillLine.line_no"
    )


class BillLine(UUIDPK, Timestamps, Base):
    __tablename__ = "bill_lines"

    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    expense_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    bill: Mapped[Bill] = relationship("Bill", back_populates="lines")


class Payment(UUIDPK, Timestamps, Base):
    __tablename__ = "payments"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[PaymentKind] = mapped_column(
        SAEnum(PaymentKind, name="payment_kind"), nullable=False, index=True
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), index=True
    )
    bill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id", ondelete="SET NULL"), index=True
    )
    posted_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL")
    )


class TaxRate(UUIDPK, Timestamps, Base):
    __tablename__ = "tax_rates"
    __table_args__ = (UniqueConstraint("entity_id", "name", name="uq_tax_rates_entity_name"),)

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(200))
    rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TaxReserve(UUIDPK, Timestamps, Base):
    __tablename__ = "tax_reserves"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    estimated_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    reserved_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(String(500))


class ClosingPeriod(UUIDPK, Timestamps, Base):
    __tablename__ = "closing_periods"
    __table_args__ = (
        UniqueConstraint("entity_id", "period_start", "period_end", name="uq_closing_periods_entity_period"),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ClosingPeriodStatus] = mapped_column(
        SAEnum(ClosingPeriodStatus, name="closing_period_status"),
        nullable=False,
        default=ClosingPeriodStatus.open,
    )
    notes: Mapped[str | None] = mapped_column(String(500))
