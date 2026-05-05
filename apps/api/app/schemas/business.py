from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import BusinessDocumentStatus, ClosingPeriodStatus, PaymentKind


def _to_decimal(value):
    if value is None or value == "":
        return None
    return Decimal(str(value))


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=500)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    name: str
    email: str | None
    notes: str | None
    is_active: bool


class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=500)


class VendorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    name: str
    email: str | None
    notes: str | None
    is_active: bool


class InvoiceLineIn(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(ge=0, decimal_places=2)
    revenue_account_id: uuid.UUID

    _coerce = field_validator("quantity", "unit_price", mode="before")(_to_decimal)


class InvoiceCreate(BaseModel):
    customer_id: uuid.UUID
    number: str = Field(min_length=1, max_length=64)
    invoice_date: date
    due_date: date
    memo: str | None = Field(default=None, max_length=500)
    lines: list[InvoiceLineIn] = Field(min_length=1)


class InvoiceUpdate(BaseModel):
    invoice_date: date | None = None
    due_date: date | None = None
    memo: str | None = Field(default=None, max_length=500)
    lines: list[InvoiceLineIn] | None = None


class InvoiceLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_no: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    revenue_account_id: uuid.UUID


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    customer_id: uuid.UUID
    number: str
    invoice_date: date
    due_date: date
    memo: str | None
    subtotal: Decimal
    total: Decimal
    balance_due: Decimal
    status: BusinessDocumentStatus
    posted_at: datetime | None
    posted_entry_id: uuid.UUID | None
    lines: list[InvoiceLineOut]


class BillLineIn(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(ge=0, decimal_places=2)
    expense_account_id: uuid.UUID

    _coerce = field_validator("quantity", "unit_price", mode="before")(_to_decimal)


class BillCreate(BaseModel):
    vendor_id: uuid.UUID
    number: str = Field(min_length=1, max_length=64)
    bill_date: date
    due_date: date
    memo: str | None = Field(default=None, max_length=500)
    lines: list[BillLineIn] = Field(min_length=1)


class BillUpdate(BaseModel):
    bill_date: date | None = None
    due_date: date | None = None
    memo: str | None = Field(default=None, max_length=500)
    lines: list[BillLineIn] | None = None


class BillLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_no: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    expense_account_id: uuid.UUID


class BillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    vendor_id: uuid.UUID
    number: str
    bill_date: date
    due_date: date
    memo: str | None
    subtotal: Decimal
    total: Decimal
    balance_due: Decimal
    status: BusinessDocumentStatus
    posted_at: datetime | None
    posted_entry_id: uuid.UUID | None
    lines: list[BillLineOut]


class ConfirmPostRequest(BaseModel):
    confirmed: bool = False


class PaymentCreate(BaseModel):
    confirmed: bool = False
    kind: PaymentKind
    payment_date: date
    amount: Decimal = Field(gt=0, decimal_places=2)
    reference: str | None = Field(default=None, max_length=100)
    invoice_id: uuid.UUID | None = None
    bill_id: uuid.UUID | None = None

    _coerce = field_validator("amount", mode="before")(_to_decimal)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    kind: PaymentKind
    payment_date: date
    amount: Decimal
    reference: str | None
    invoice_id: uuid.UUID | None
    bill_id: uuid.UUID | None
    posted_entry_id: uuid.UUID | None


class AgingRow(BaseModel):
    object_id: uuid.UUID
    number: str
    counterparty_name: str
    due_date: date
    balance_due: Decimal
    current: Decimal
    days_1_30: Decimal
    days_31_60: Decimal
    days_61_90: Decimal
    days_91_plus: Decimal


class AgingReportOut(BaseModel):
    entity_id: uuid.UUID
    as_of: date
    total_balance_due: Decimal
    rows: list[AgingRow]


class StatementRow(BaseModel):
    account_id: uuid.UUID
    code: str
    name: str
    amount: Decimal


class BalanceSheetOut(BaseModel):
    entity_id: uuid.UUID
    as_of: date
    assets: list[StatementRow]
    liabilities: list[StatementRow]
    equity: list[StatementRow]
    current_earnings: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    is_balanced: bool


class IncomeStatementOut(BaseModel):
    entity_id: uuid.UUID
    date_from: date
    date_to: date
    income: list[StatementRow]
    expenses: list[StatementRow]
    total_income: Decimal
    total_expenses: Decimal
    net_income: Decimal


class CashFlowOut(BaseModel):
    entity_id: uuid.UUID
    date_from: date
    date_to: date
    rows: list[StatementRow]
    total_cash_change: Decimal


class BusinessDashboardOut(BaseModel):
    entity_id: uuid.UUID
    as_of: date
    month_start: date
    month_end: date
    cash_balance: Decimal
    accounts_receivable: Decimal
    accounts_payable: Decimal
    tax_reserve_balance: Decimal
    monthly_revenue: Decimal
    monthly_expenses: Decimal
    monthly_net_income: Decimal
    open_invoices: int
    open_bills: int
    tax_estimate_note: str


class ClosingChecklistOut(BaseModel):
    entity_id: uuid.UUID
    as_of: date
    trial_balance_balanced: bool
    open_invoices: int
    open_bills: int
    tax_reserve_balance: Decimal
    checklist: list[str]


class TaxRateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    jurisdiction: str | None = Field(default=None, max_length=200)
    rate: Decimal = Field(ge=0)

    _coerce = field_validator("rate", mode="before")(_to_decimal)


class TaxRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    name: str
    jurisdiction: str | None
    rate: Decimal
    is_active: bool


class TaxReserveCreate(BaseModel):
    as_of: date
    estimated_tax: Decimal = Field(ge=0, decimal_places=2)
    reserved_amount: Decimal = Field(ge=0, decimal_places=2)
    notes: str | None = Field(default=None, max_length=500)

    _coerce = field_validator("estimated_tax", "reserved_amount", mode="before")(_to_decimal)


class TaxReserveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    as_of: date
    estimated_tax: Decimal
    reserved_amount: Decimal
    notes: str | None


class ClosingPeriodCreate(BaseModel):
    period_start: date
    period_end: date
    status: ClosingPeriodStatus = ClosingPeriodStatus.open
    notes: str | None = Field(default=None, max_length=500)


class ClosingPeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    period_start: date
    period_end: date
    status: ClosingPeriodStatus
    notes: str | None
