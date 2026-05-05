from __future__ import annotations

import calendar
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import ConflictError, FinClawError, NotFoundError
from app.models import (
    Account,
    AccountType,
    Bill,
    BillLine,
    BusinessDocumentStatus,
    ClosingPeriod,
    Customer,
    Entity,
    EntityMode,
    Invoice,
    InvoiceLine,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
    NormalSide,
    Payment,
    PaymentKind,
    TaxRate,
    TaxReserve,
    Vendor,
)
from app.models.base import utcnow
from app.money import ZERO, to_money
from app.schemas.business import (
    AgingReportOut,
    AgingRow,
    BalanceSheetOut,
    BillCreate,
    BillLineIn,
    BillUpdate,
    BusinessDashboardOut,
    CashFlowOut,
    ClosingChecklistOut,
    ClosingPeriodCreate,
    CustomerCreate,
    CustomerUpdate,
    IncomeStatementOut,
    InvoiceCreate,
    InvoiceLineIn,
    InvoiceUpdate,
    PaymentCreate,
    StatementRow,
    TaxRateCreate,
    TaxReserveCreate,
    VendorCreate,
    VendorUpdate,
)
from app.schemas.journal import JournalEntryCreate, JournalLineIn
from app.services.journal import create_draft, post_entry

TAX_ESTIMATE_NOTE = "Tax reserve figures are estimates until a jurisdiction-specific tax configuration is set."


async def _get_business_entity(db: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = await db.get(Entity, entity_id)
    if entity is None:
        raise NotFoundError(f"Entity {entity_id} not found", code="entity_not_found")
    if entity.mode != EntityMode.business:
        raise FinClawError(
            "This endpoint is only available for business entities",
            code="entity_not_business",
        )
    return entity


def _month_bounds(as_of: date) -> tuple[date, date]:
    start = as_of.replace(day=1)
    end = as_of.replace(day=calendar.monthrange(as_of.year, as_of.month)[1])
    return start, end


def _signed_balance(debit: Decimal, credit: Decimal, normal_side: NormalSide) -> Decimal:
    if normal_side == NormalSide.debit:
        return to_money(debit - credit)
    return to_money(credit - debit)


async def _get_accounts(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    account_ids: list[uuid.UUID] | None = None,
) -> dict[uuid.UUID, Account]:
    filters = [Account.entity_id == entity_id]
    if account_ids:
        filters.append(Account.id.in_(account_ids))
    rows = (await db.execute(select(Account).where(*filters))).scalars().all()
    out = {row.id: row for row in rows}
    if account_ids:
        missing = set(account_ids) - set(out)
        if missing:
            raise NotFoundError(
                f"Account(s) not found: {sorted(str(item) for item in missing)}",
                code="account_not_found",
            )
    return out


async def _account_by_code(db: AsyncSession, *, entity_id: uuid.UUID, code: str) -> Account:
    account = (
        await db.execute(
            select(Account).where(Account.entity_id == entity_id, Account.code == code)
        )
    ).scalar_one_or_none()
    if account is None:
        raise NotFoundError(f"Required account code {code} not found", code="account_not_found")
    return account


async def _ledger_balances(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[uuid.UUID, dict]:
    filters = [
        Account.entity_id == entity_id,
        JournalEntry.entity_id == entity_id,
        JournalEntry.status.in_([JournalEntryStatus.posted, JournalEntryStatus.voided]),
    ]
    if date_from is not None:
        filters.append(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        filters.append(JournalEntry.entry_date <= date_to)
    rows = (
        await db.execute(
            select(
                Account.id,
                Account.code,
                Account.name,
                Account.type,
                Account.normal_side,
                func.coalesce(func.sum(JournalLine.debit), 0).label("debit"),
                func.coalesce(func.sum(JournalLine.credit), 0).label("credit"),
            )
            .join(JournalLine, JournalLine.account_id == Account.id)
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(*filters)
            .group_by(Account.id)
            .order_by(Account.code)
        )
    ).all()
    out: dict[uuid.UUID, dict] = {}
    for row in rows:
        out[row.id] = {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "type": row.type,
            "normal_side": row.normal_side,
            "amount": _signed_balance(Decimal(row.debit), Decimal(row.credit), row.normal_side),
        }
    return out


async def _assert_customer(db: AsyncSession, *, entity_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
    customer = await db.get(Customer, customer_id)
    if customer is None or customer.entity_id != entity_id:
        raise NotFoundError(f"Customer {customer_id} not found", code="customer_not_found")
    return customer


async def _assert_vendor(db: AsyncSession, *, entity_id: uuid.UUID, vendor_id: uuid.UUID) -> Vendor:
    vendor = await db.get(Vendor, vendor_id)
    if vendor is None or vendor.entity_id != entity_id:
        raise NotFoundError(f"Vendor {vendor_id} not found", code="vendor_not_found")
    return vendor


def _invoice_totals(lines: list[InvoiceLineIn]) -> tuple[Decimal, list[dict]]:
    built: list[dict] = []
    total = ZERO
    for idx, line in enumerate(lines, start=1):
        amount = to_money(line.quantity * line.unit_price)
        total += amount
        built.append(
            {
                "line_no": idx,
                "description": line.description,
                "quantity": line.quantity,
                "unit_price": to_money(line.unit_price),
                "amount": amount,
                "revenue_account_id": line.revenue_account_id,
            }
        )
    return to_money(total), built


def _bill_totals(lines: list[BillLineIn]) -> tuple[Decimal, list[dict]]:
    built: list[dict] = []
    total = ZERO
    for idx, line in enumerate(lines, start=1):
        amount = to_money(line.quantity * line.unit_price)
        total += amount
        built.append(
            {
                "line_no": idx,
                "description": line.description,
                "quantity": line.quantity,
                "unit_price": to_money(line.unit_price),
                "amount": amount,
                "expense_account_id": line.expense_account_id,
            }
        )
    return to_money(total), built


async def list_customers(db: AsyncSession, *, entity_id: uuid.UUID) -> list[Customer]:
    await _get_business_entity(db, entity_id)
    rows = (
        await db.execute(select(Customer).where(Customer.entity_id == entity_id).order_by(Customer.name))
    ).scalars()
    return list(rows)


async def create_customer(db: AsyncSession, *, entity_id: uuid.UUID, payload: CustomerCreate) -> Customer:
    await _get_business_entity(db, entity_id)
    customer = Customer(entity_id=entity_id, name=payload.name, email=payload.email, notes=payload.notes)
    db.add(customer)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("Customer already exists", code="duplicate_customer") from exc
    return customer


async def get_customer(db: AsyncSession, *, entity_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
    await _get_business_entity(db, entity_id)
    return await _assert_customer(db, entity_id=entity_id, customer_id=customer_id)


async def update_customer(db: AsyncSession, customer: Customer, *, payload: CustomerUpdate) -> Customer:
    if payload.name is not None:
        customer.name = payload.name
    if payload.email is not None:
        customer.email = payload.email
    if payload.notes is not None:
        customer.notes = payload.notes
    if payload.is_active is not None:
        customer.is_active = payload.is_active
    await db.flush()
    return customer


async def delete_customer(db: AsyncSession, customer: Customer) -> None:
    await db.delete(customer)
    await db.flush()


async def list_vendors(db: AsyncSession, *, entity_id: uuid.UUID) -> list[Vendor]:
    await _get_business_entity(db, entity_id)
    rows = (
        await db.execute(select(Vendor).where(Vendor.entity_id == entity_id).order_by(Vendor.name))
    ).scalars()
    return list(rows)


async def create_vendor(db: AsyncSession, *, entity_id: uuid.UUID, payload: VendorCreate) -> Vendor:
    await _get_business_entity(db, entity_id)
    vendor = Vendor(entity_id=entity_id, name=payload.name, email=payload.email, notes=payload.notes)
    db.add(vendor)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("Vendor already exists", code="duplicate_vendor") from exc
    return vendor


async def get_vendor(db: AsyncSession, *, entity_id: uuid.UUID, vendor_id: uuid.UUID) -> Vendor:
    await _get_business_entity(db, entity_id)
    return await _assert_vendor(db, entity_id=entity_id, vendor_id=vendor_id)


async def update_vendor(db: AsyncSession, vendor: Vendor, *, payload: VendorUpdate) -> Vendor:
    if payload.name is not None:
        vendor.name = payload.name
    if payload.email is not None:
        vendor.email = payload.email
    if payload.notes is not None:
        vendor.notes = payload.notes
    if payload.is_active is not None:
        vendor.is_active = payload.is_active
    await db.flush()
    return vendor


async def delete_vendor(db: AsyncSession, vendor: Vendor) -> None:
    await db.delete(vendor)
    await db.flush()


async def create_invoice(db: AsyncSession, *, entity_id: uuid.UUID, payload: InvoiceCreate) -> Invoice:
    await _get_business_entity(db, entity_id)
    await _assert_customer(db, entity_id=entity_id, customer_id=payload.customer_id)
    if payload.due_date < payload.invoice_date:
        raise FinClawError("due_date must be on or after invoice_date", code="invalid_due_date")
    total, built_lines = _invoice_totals(payload.lines)
    accounts = await _get_accounts(
        db, entity_id=entity_id, account_ids=[line["revenue_account_id"] for line in built_lines]
    )
    for account in accounts.values():
        if account.type != AccountType.income:
            raise FinClawError("Invoice lines must post to income accounts", code="invoice_account_not_income")
    invoice = Invoice(
        entity_id=entity_id,
        customer_id=payload.customer_id,
        number=payload.number,
        invoice_date=payload.invoice_date,
        due_date=payload.due_date,
        memo=payload.memo,
        subtotal=total,
        total=total,
        balance_due=total,
        status=BusinessDocumentStatus.draft,
    )
    db.add(invoice)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("Invoice number already exists", code="duplicate_invoice_number") from exc
    for line in built_lines:
        db.add(InvoiceLine(invoice_id=invoice.id, **line))
    await db.flush()
    await db.refresh(invoice, attribute_names=["lines"])
    return invoice


async def get_invoice(db: AsyncSession, *, entity_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    await _get_business_entity(db, entity_id)
    invoice = (
        await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.lines))
            .where(Invoice.id == invoice_id, Invoice.entity_id == entity_id)
        )
    ).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError(f"Invoice {invoice_id} not found", code="invoice_not_found")
    return invoice


async def list_invoices(db: AsyncSession, *, entity_id: uuid.UUID) -> list[Invoice]:
    await _get_business_entity(db, entity_id)
    rows = (
        await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.lines))
            .where(Invoice.entity_id == entity_id)
            .order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())
        )
    ).scalars()
    return list(rows)


async def update_invoice(db: AsyncSession, invoice: Invoice, *, payload: InvoiceUpdate) -> Invoice:
    if invoice.status != BusinessDocumentStatus.draft:
        raise FinClawError("Only draft invoices can be edited", code="invoice_not_draft")
    if payload.invoice_date is not None:
        invoice.invoice_date = payload.invoice_date
    if payload.due_date is not None:
        invoice.due_date = payload.due_date
    if invoice.due_date < invoice.invoice_date:
        raise FinClawError("due_date must be on or after invoice_date", code="invalid_due_date")
    if payload.memo is not None:
        invoice.memo = payload.memo
    if payload.lines is not None:
        total, built_lines = _invoice_totals(payload.lines)
        accounts = await _get_accounts(
            db, entity_id=invoice.entity_id, account_ids=[line["revenue_account_id"] for line in built_lines]
        )
        for account in accounts.values():
            if account.type != AccountType.income:
                raise FinClawError("Invoice lines must post to income accounts", code="invoice_account_not_income")
        for existing in list(invoice.lines):
            await db.delete(existing)
        await db.flush()
        for line in built_lines:
            db.add(InvoiceLine(invoice_id=invoice.id, **line))
        invoice.subtotal = total
        invoice.total = total
        invoice.balance_due = total
    await db.flush()
    await db.refresh(invoice, attribute_names=["lines"])
    return invoice


async def post_invoice(
    db: AsyncSession,
    invoice: Invoice,
    *,
    user_id: uuid.UUID,
    confirmed: bool,
) -> Invoice:
    if not confirmed:
        raise FinClawError("Posting an invoice requires explicit confirmation", code="confirmation_required")
    if invoice.status != BusinessDocumentStatus.draft:
        raise FinClawError("Only draft invoices can be posted", code="invoice_not_draft")
    ar = await _account_by_code(db, entity_id=invoice.entity_id, code="1200")
    payload = JournalEntryCreate(
        entry_date=invoice.invoice_date,
        memo=f"Invoice {invoice.number}",
        lines=[
            JournalLineIn(account_id=ar.id, debit=invoice.total, credit=ZERO),
            *[
                JournalLineIn(account_id=line.revenue_account_id, debit=ZERO, credit=line.amount, description=line.description)
                for line in invoice.lines
            ],
        ],
    )
    entry = await create_draft(db, entity_id=invoice.entity_id, user_id=user_id, payload=payload)
    posted = await post_entry(db, entry, posted_by_id=user_id)
    invoice.status = BusinessDocumentStatus.posted
    invoice.posted_at = utcnow()
    invoice.posted_entry_id = posted.id
    await db.flush()
    return invoice


async def create_bill(db: AsyncSession, *, entity_id: uuid.UUID, payload: BillCreate) -> Bill:
    await _get_business_entity(db, entity_id)
    await _assert_vendor(db, entity_id=entity_id, vendor_id=payload.vendor_id)
    if payload.due_date < payload.bill_date:
        raise FinClawError("due_date must be on or after bill_date", code="invalid_due_date")
    total, built_lines = _bill_totals(payload.lines)
    accounts = await _get_accounts(
        db, entity_id=entity_id, account_ids=[line["expense_account_id"] for line in built_lines]
    )
    for account in accounts.values():
        if account.type not in (AccountType.expense, AccountType.asset):
            raise FinClawError("Bill lines must post to expense or asset accounts", code="bill_account_invalid_type")
    bill = Bill(
        entity_id=entity_id,
        vendor_id=payload.vendor_id,
        number=payload.number,
        bill_date=payload.bill_date,
        due_date=payload.due_date,
        memo=payload.memo,
        subtotal=total,
        total=total,
        balance_due=total,
        status=BusinessDocumentStatus.draft,
    )
    db.add(bill)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("Bill number already exists", code="duplicate_bill_number") from exc
    for line in built_lines:
        db.add(BillLine(bill_id=bill.id, **line))
    await db.flush()
    await db.refresh(bill, attribute_names=["lines"])
    return bill


async def get_bill(db: AsyncSession, *, entity_id: uuid.UUID, bill_id: uuid.UUID) -> Bill:
    await _get_business_entity(db, entity_id)
    bill = (
        await db.execute(
            select(Bill)
            .options(selectinload(Bill.lines))
            .where(Bill.id == bill_id, Bill.entity_id == entity_id)
        )
    ).scalar_one_or_none()
    if bill is None:
        raise NotFoundError(f"Bill {bill_id} not found", code="bill_not_found")
    return bill


async def list_bills(db: AsyncSession, *, entity_id: uuid.UUID) -> list[Bill]:
    await _get_business_entity(db, entity_id)
    rows = (
        await db.execute(
            select(Bill)
            .options(selectinload(Bill.lines))
            .where(Bill.entity_id == entity_id)
            .order_by(Bill.bill_date.desc(), Bill.created_at.desc())
        )
    ).scalars()
    return list(rows)


async def update_bill(db: AsyncSession, bill: Bill, *, payload: BillUpdate) -> Bill:
    if bill.status != BusinessDocumentStatus.draft:
        raise FinClawError("Only draft bills can be edited", code="bill_not_draft")
    if payload.bill_date is not None:
        bill.bill_date = payload.bill_date
    if payload.due_date is not None:
        bill.due_date = payload.due_date
    if bill.due_date < bill.bill_date:
        raise FinClawError("due_date must be on or after bill_date", code="invalid_due_date")
    if payload.memo is not None:
        bill.memo = payload.memo
    if payload.lines is not None:
        total, built_lines = _bill_totals(payload.lines)
        accounts = await _get_accounts(
            db, entity_id=bill.entity_id, account_ids=[line["expense_account_id"] for line in built_lines]
        )
        for account in accounts.values():
            if account.type not in (AccountType.expense, AccountType.asset):
                raise FinClawError("Bill lines must post to expense or asset accounts", code="bill_account_invalid_type")
        for existing in list(bill.lines):
            await db.delete(existing)
        await db.flush()
        for line in built_lines:
            db.add(BillLine(bill_id=bill.id, **line))
        bill.subtotal = total
        bill.total = total
        bill.balance_due = total
    await db.flush()
    await db.refresh(bill, attribute_names=["lines"])
    return bill


async def post_bill(
    db: AsyncSession,
    bill: Bill,
    *,
    user_id: uuid.UUID,
    confirmed: bool,
) -> Bill:
    if not confirmed:
        raise FinClawError("Posting a bill requires explicit confirmation", code="confirmation_required")
    if bill.status != BusinessDocumentStatus.draft:
        raise FinClawError("Only draft bills can be posted", code="bill_not_draft")
    ap = await _account_by_code(db, entity_id=bill.entity_id, code="2100")
    payload = JournalEntryCreate(
        entry_date=bill.bill_date,
        memo=f"Bill {bill.number}",
        lines=[
            *[
                JournalLineIn(account_id=line.expense_account_id, debit=line.amount, credit=ZERO, description=line.description)
                for line in bill.lines
            ],
            JournalLineIn(account_id=ap.id, debit=ZERO, credit=bill.total),
        ],
    )
    entry = await create_draft(db, entity_id=bill.entity_id, user_id=user_id, payload=payload)
    posted = await post_entry(db, entry, posted_by_id=user_id)
    bill.status = BusinessDocumentStatus.posted
    bill.posted_at = utcnow()
    bill.posted_entry_id = posted.id
    await db.flush()
    return bill


async def record_payment(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: PaymentCreate,
) -> Payment:
    await _get_business_entity(db, entity_id)
    if not payload.confirmed:
        raise FinClawError("Recording a payment requires explicit confirmation", code="confirmation_required")
    cash = await _account_by_code(db, entity_id=entity_id, code="1110")
    ar = await _account_by_code(db, entity_id=entity_id, code="1200")
    ap = await _account_by_code(db, entity_id=entity_id, code="2100")

    if payload.kind == PaymentKind.customer_receipt:
        if payload.invoice_id is None or payload.bill_id is not None:
            raise FinClawError("Customer receipt must reference invoice_id only", code="invalid_payment_target")
        invoice = await get_invoice(db, entity_id=entity_id, invoice_id=payload.invoice_id)
        if invoice.status not in (BusinessDocumentStatus.posted, BusinessDocumentStatus.partial):
            raise FinClawError("Invoice is not open for payment", code="invoice_not_open")
        if payload.amount > invoice.balance_due:
            raise FinClawError("Payment exceeds invoice balance due", code="payment_exceeds_balance")
        journal_lines = [
            JournalLineIn(account_id=cash.id, debit=payload.amount, credit=ZERO),
            JournalLineIn(account_id=ar.id, debit=ZERO, credit=payload.amount),
        ]
    else:
        if payload.bill_id is None or payload.invoice_id is not None:
            raise FinClawError("Vendor payment must reference bill_id only", code="invalid_payment_target")
        bill = await get_bill(db, entity_id=entity_id, bill_id=payload.bill_id)
        if bill.status not in (BusinessDocumentStatus.posted, BusinessDocumentStatus.partial):
            raise FinClawError("Bill is not open for payment", code="bill_not_open")
        if payload.amount > bill.balance_due:
            raise FinClawError("Payment exceeds bill balance due", code="payment_exceeds_balance")
        journal_lines = [
            JournalLineIn(account_id=ap.id, debit=payload.amount, credit=ZERO),
            JournalLineIn(account_id=cash.id, debit=ZERO, credit=payload.amount),
        ]

    entry = await create_draft(
        db,
        entity_id=entity_id,
        user_id=user_id,
        payload=JournalEntryCreate(
            entry_date=payload.payment_date,
            memo=payload.reference or payload.kind.value,
            lines=journal_lines,
        ),
    )
    posted = await post_entry(db, entry, posted_by_id=user_id)
    payment = Payment(
        entity_id=entity_id,
        kind=payload.kind,
        payment_date=payload.payment_date,
        amount=to_money(payload.amount),
        reference=payload.reference,
        invoice_id=payload.invoice_id,
        bill_id=payload.bill_id,
        posted_entry_id=posted.id,
    )
    db.add(payment)
    await db.flush()

    if payload.kind == PaymentKind.customer_receipt:
        invoice.balance_due = to_money(invoice.balance_due - payload.amount)
        invoice.status = BusinessDocumentStatus.paid if invoice.balance_due == ZERO else BusinessDocumentStatus.partial
    else:
        bill.balance_due = to_money(bill.balance_due - payload.amount)
        bill.status = BusinessDocumentStatus.paid if bill.balance_due == ZERO else BusinessDocumentStatus.partial
    await db.flush()
    return payment


async def list_payments(db: AsyncSession, *, entity_id: uuid.UUID) -> list[Payment]:
    await _get_business_entity(db, entity_id)
    rows = (
        await db.execute(
            select(Payment).where(Payment.entity_id == entity_id).order_by(Payment.payment_date.desc(), Payment.created_at.desc())
        )
    ).scalars()
    return list(rows)


def _aging_bucket(*, due_date: date, as_of: date, balance: Decimal) -> dict[str, Decimal]:
    days = (as_of - due_date).days
    buckets = {
        "current": ZERO,
        "days_1_30": ZERO,
        "days_31_60": ZERO,
        "days_61_90": ZERO,
        "days_91_plus": ZERO,
    }
    if days <= 0:
        buckets["current"] = balance
    elif days <= 30:
        buckets["days_1_30"] = balance
    elif days <= 60:
        buckets["days_31_60"] = balance
    elif days <= 90:
        buckets["days_61_90"] = balance
    else:
        buckets["days_91_plus"] = balance
    return buckets


async def ar_aging(db: AsyncSession, *, entity_id: uuid.UUID, as_of: date) -> AgingReportOut:
    await _get_business_entity(db, entity_id)
    invoices = (
        await db.execute(
            select(Invoice, Customer)
            .join(Customer, Customer.id == Invoice.customer_id)
            .where(
                Invoice.entity_id == entity_id,
                Invoice.status.in_([BusinessDocumentStatus.posted, BusinessDocumentStatus.partial]),
                Invoice.balance_due > 0,
            )
            .order_by(Invoice.due_date)
        )
    ).all()
    rows: list[AgingRow] = []
    total = ZERO
    for invoice, customer in invoices:
        balance = to_money(invoice.balance_due)
        total += balance
        rows.append(
            AgingRow(
                object_id=invoice.id,
                number=invoice.number,
                counterparty_name=customer.name,
                due_date=invoice.due_date,
                balance_due=balance,
                **_aging_bucket(due_date=invoice.due_date, as_of=as_of, balance=balance),
            )
        )
    return AgingReportOut(entity_id=entity_id, as_of=as_of, total_balance_due=to_money(total), rows=rows)


async def ap_aging(db: AsyncSession, *, entity_id: uuid.UUID, as_of: date) -> AgingReportOut:
    await _get_business_entity(db, entity_id)
    bills = (
        await db.execute(
            select(Bill, Vendor)
            .join(Vendor, Vendor.id == Bill.vendor_id)
            .where(
                Bill.entity_id == entity_id,
                Bill.status.in_([BusinessDocumentStatus.posted, BusinessDocumentStatus.partial]),
                Bill.balance_due > 0,
            )
            .order_by(Bill.due_date)
        )
    ).all()
    rows: list[AgingRow] = []
    total = ZERO
    for bill, vendor in bills:
        balance = to_money(bill.balance_due)
        total += balance
        rows.append(
            AgingRow(
                object_id=bill.id,
                number=bill.number,
                counterparty_name=vendor.name,
                due_date=bill.due_date,
                balance_due=balance,
                **_aging_bucket(due_date=bill.due_date, as_of=as_of, balance=balance),
            )
        )
    return AgingReportOut(entity_id=entity_id, as_of=as_of, total_balance_due=to_money(total), rows=rows)


async def income_statement(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> IncomeStatementOut:
    await _get_business_entity(db, entity_id)
    balances = await _ledger_balances(db, entity_id=entity_id, date_from=date_from, date_to=date_to)
    income_rows: list[StatementRow] = []
    expense_rows: list[StatementRow] = []
    total_income = ZERO
    total_expenses = ZERO
    for row in balances.values():
        amount = to_money(row["amount"])
        if row["type"] == AccountType.income:
            income_rows.append(StatementRow(account_id=row["id"], code=row["code"], name=row["name"], amount=amount))
            total_income += amount
        elif row["type"] == AccountType.expense:
            expense_rows.append(StatementRow(account_id=row["id"], code=row["code"], name=row["name"], amount=amount))
            total_expenses += amount
    total_income = to_money(total_income)
    total_expenses = to_money(total_expenses)
    return IncomeStatementOut(
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        income=income_rows,
        expenses=expense_rows,
        total_income=total_income,
        total_expenses=total_expenses,
        net_income=to_money(total_income - total_expenses),
    )


async def balance_sheet(db: AsyncSession, *, entity_id: uuid.UUID, as_of: date) -> BalanceSheetOut:
    await _get_business_entity(db, entity_id)
    balances = await _ledger_balances(db, entity_id=entity_id, date_to=as_of)
    assets: list[StatementRow] = []
    liabilities: list[StatementRow] = []
    equity: list[StatementRow] = []
    total_assets = ZERO
    total_liabilities = ZERO
    raw_equity = ZERO
    current_earnings = ZERO
    for row in balances.values():
        amount = to_money(row["amount"])
        if row["type"] == AccountType.asset:
            assets.append(StatementRow(account_id=row["id"], code=row["code"], name=row["name"], amount=amount))
            total_assets += amount
        elif row["type"] == AccountType.liability:
            liabilities.append(StatementRow(account_id=row["id"], code=row["code"], name=row["name"], amount=amount))
            total_liabilities += amount
        elif row["type"] == AccountType.equity:
            equity.append(StatementRow(account_id=row["id"], code=row["code"], name=row["name"], amount=amount))
            raw_equity += amount
        elif row["type"] == AccountType.income:
            current_earnings += amount
        elif row["type"] == AccountType.expense:
            current_earnings -= amount
    total_assets = to_money(total_assets)
    total_liabilities = to_money(total_liabilities)
    current_earnings = to_money(current_earnings)
    total_equity = to_money(raw_equity + current_earnings)
    return BalanceSheetOut(
        entity_id=entity_id,
        as_of=as_of,
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        current_earnings=current_earnings,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_equity=total_equity,
        is_balanced=(total_assets == to_money(total_liabilities + total_equity)),
    )


async def cash_flow_statement(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> CashFlowOut:
    await _get_business_entity(db, entity_id)
    balances = await _ledger_balances(db, entity_id=entity_id, date_from=date_from, date_to=date_to)
    rows: list[StatementRow] = []
    total = ZERO
    for row in balances.values():
        if row["type"] != AccountType.asset or not row["code"].startswith("11"):
            continue
        amount = to_money(row["amount"])
        total += amount
        rows.append(StatementRow(account_id=row["id"], code=row["code"], name=row["name"], amount=amount))
    return CashFlowOut(
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        rows=rows,
        total_cash_change=to_money(total),
    )


async def business_dashboard(db: AsyncSession, *, entity_id: uuid.UUID, as_of: date) -> BusinessDashboardOut:
    await _get_business_entity(db, entity_id)
    month_start, month_end = _month_bounds(as_of)
    cumulative = await _ledger_balances(db, entity_id=entity_id, date_to=as_of)
    month_is = await income_statement(db, entity_id=entity_id, date_from=month_start, date_to=min(month_end, as_of))
    open_invoices = len((await ar_aging(db, entity_id=entity_id, as_of=as_of)).rows)
    open_bills = len((await ap_aging(db, entity_id=entity_id, as_of=as_of)).rows)
    cash_balance = ZERO
    ar_balance = ZERO
    ap_balance = ZERO
    tax_reserve_balance = ZERO
    for row in cumulative.values():
        if row["code"] == "1110":
            cash_balance = to_money(row["amount"])
        elif row["code"] == "1200":
            ar_balance = to_money(row["amount"])
        elif row["code"] == "2100":
            ap_balance = to_money(row["amount"])
        elif row["code"] == "2200":
            tax_reserve_balance = to_money(row["amount"])
    return BusinessDashboardOut(
        entity_id=entity_id,
        as_of=as_of,
        month_start=month_start,
        month_end=month_end,
        cash_balance=cash_balance,
        accounts_receivable=ar_balance,
        accounts_payable=ap_balance,
        tax_reserve_balance=tax_reserve_balance,
        monthly_revenue=month_is.total_income,
        monthly_expenses=month_is.total_expenses,
        monthly_net_income=month_is.net_income,
        open_invoices=open_invoices,
        open_bills=open_bills,
        tax_estimate_note=TAX_ESTIMATE_NOTE,
    )


async def create_tax_rate(db: AsyncSession, *, entity_id: uuid.UUID, payload: TaxRateCreate) -> TaxRate:
    await _get_business_entity(db, entity_id)
    row = TaxRate(entity_id=entity_id, name=payload.name, jurisdiction=payload.jurisdiction, rate=payload.rate)
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("Tax rate already exists", code="duplicate_tax_rate") from exc
    return row


async def list_tax_rates(db: AsyncSession, *, entity_id: uuid.UUID) -> list[TaxRate]:
    await _get_business_entity(db, entity_id)
    rows = (await db.execute(select(TaxRate).where(TaxRate.entity_id == entity_id).order_by(TaxRate.name))).scalars()
    return list(rows)


async def create_tax_reserve(db: AsyncSession, *, entity_id: uuid.UUID, payload: TaxReserveCreate) -> TaxReserve:
    await _get_business_entity(db, entity_id)
    row = TaxReserve(
        entity_id=entity_id,
        as_of=payload.as_of,
        estimated_tax=to_money(payload.estimated_tax),
        reserved_amount=to_money(payload.reserved_amount),
        notes=payload.notes,
    )
    db.add(row)
    await db.flush()
    return row


async def list_tax_reserves(db: AsyncSession, *, entity_id: uuid.UUID) -> list[TaxReserve]:
    await _get_business_entity(db, entity_id)
    rows = (
        await db.execute(select(TaxReserve).where(TaxReserve.entity_id == entity_id).order_by(TaxReserve.as_of.desc()))
    ).scalars()
    return list(rows)


async def create_closing_period(db: AsyncSession, *, entity_id: uuid.UUID, payload: ClosingPeriodCreate) -> ClosingPeriod:
    await _get_business_entity(db, entity_id)
    if payload.period_end < payload.period_start:
        raise FinClawError("period_end must be on or after period_start", code="invalid_closing_period")
    row = ClosingPeriod(
        entity_id=entity_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        status=payload.status,
        notes=payload.notes,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("Closing period already exists", code="duplicate_closing_period") from exc
    return row


async def list_closing_periods(db: AsyncSession, *, entity_id: uuid.UUID) -> list[ClosingPeriod]:
    await _get_business_entity(db, entity_id)
    rows = (
        await db.execute(
            select(ClosingPeriod).where(ClosingPeriod.entity_id == entity_id).order_by(ClosingPeriod.period_start.desc())
        )
    ).scalars()
    return list(rows)


async def closing_checklist(db: AsyncSession, *, entity_id: uuid.UUID, as_of: date) -> ClosingChecklistOut:
    await _get_business_entity(db, entity_id)
    bs = await balance_sheet(db, entity_id=entity_id, as_of=as_of)
    ar = await ar_aging(db, entity_id=entity_id, as_of=as_of)
    ap = await ap_aging(db, entity_id=entity_id, as_of=as_of)
    dashboard = await business_dashboard(db, entity_id=entity_id, as_of=as_of)
    checklist = [
        "Trial balance is balanced" if bs.is_balanced else "Trial balance or balance sheet is out of balance",
        f"Open invoices: {len(ar.rows)}",
        f"Open bills: {len(ap.rows)}",
        f"Tax reserve balance: {dashboard.tax_reserve_balance}",
    ]
    return ClosingChecklistOut(
        entity_id=entity_id,
        as_of=as_of,
        trial_balance_balanced=bs.is_balanced,
        open_invoices=len(ar.rows),
        open_bills=len(ap.rows),
        tax_reserve_balance=dashboard.tax_reserve_balance,
        checklist=checklist,
    )
