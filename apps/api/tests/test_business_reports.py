from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Account, BusinessDocumentStatus, PaymentKind
from app.schemas.business import BillCreate, CustomerCreate, InvoiceCreate, PaymentCreate, VendorCreate
from app.services.business import (
    ap_aging,
    ar_aging,
    balance_sheet,
    business_dashboard,
    cash_flow_statement,
    create_bill,
    create_customer,
    create_invoice,
    create_vendor,
    explain_business_profitability,
    explain_cash_flow_risk,
    expenses_by_vendor,
    gross_margin_report,
    income_statement,
    post_bill,
    post_invoice,
    record_payment,
    revenue_by_customer,
    runway_report,
    tax_reserve_report,
)

pytestmark = pytest.mark.asyncio


async def _accounts(db, entity_id: uuid.UUID) -> dict[str, Account]:
    rows = (await db.execute(select(Account).where(Account.entity_id == entity_id))).scalars().all()
    return {a.code: a for a in rows}


async def test_customer_invoice_payment_and_ar_aging(seeded, db):
    entity_id = uuid.UUID(seeded["business_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)

    customer = await create_customer(db, entity_id=entity_id, payload=CustomerCreate(name="Acme"))
    invoice = await create_invoice(
        db,
        entity_id=entity_id,
        payload=InvoiceCreate(
            customer_id=customer.id,
            number="INV-001",
            invoice_date=date(2026, 5, 1),
            due_date=date(2026, 5, 15),
            lines=[{"description": "Consulting", "quantity": "1", "unit_price": "1000.00", "revenue_account_id": accounts["4200"].id}],
        ),
    )
    invoice = await post_invoice(db, invoice, user_id=user_id, confirmed=True)
    assert invoice.status == BusinessDocumentStatus.posted

    ar_before = await ar_aging(db, entity_id=entity_id, as_of=date(2026, 5, 20))
    assert ar_before.total_balance_due == Decimal("1000.00")
    assert ar_before.rows[0].days_1_30 == Decimal("1000.00")

    payment = await record_payment(
        db,
        entity_id=entity_id,
        user_id=user_id,
        payload=PaymentCreate(
            confirmed=True,
            kind=PaymentKind.customer_receipt,
            payment_date=date(2026, 5, 21),
            amount=Decimal("1000.00"),
            invoice_id=invoice.id,
        ),
    )
    assert payment.kind == PaymentKind.customer_receipt

    ar_after = await ar_aging(db, entity_id=entity_id, as_of=date(2026, 5, 21))
    assert ar_after.total_balance_due == Decimal("0.00")
    assert ar_after.rows == []


async def test_vendor_bill_payment_and_ap_aging(seeded, db):
    entity_id = uuid.UUID(seeded["business_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)

    vendor = await create_vendor(db, entity_id=entity_id, payload=VendorCreate(name="Office Supply Co"))
    bill = await create_bill(
        db,
        entity_id=entity_id,
        payload=BillCreate(
            vendor_id=vendor.id,
            number="BILL-001",
            bill_date=date(2026, 5, 1),
            due_date=date(2026, 5, 10),
            lines=[{"description": "Supplies", "quantity": "1", "unit_price": "300.00", "expense_account_id": accounts["6500"].id}],
        ),
    )
    bill = await post_bill(db, bill, user_id=user_id, confirmed=True)
    assert bill.status == BusinessDocumentStatus.posted

    ap_before = await ap_aging(db, entity_id=entity_id, as_of=date(2026, 5, 20))
    assert ap_before.total_balance_due == Decimal("300.00")
    assert ap_before.rows[0].days_1_30 == Decimal("300.00")

    payment = await record_payment(
        db,
        entity_id=entity_id,
        user_id=user_id,
        payload=PaymentCreate(
            confirmed=True,
            kind=PaymentKind.vendor_payment,
            payment_date=date(2026, 5, 21),
            amount=Decimal("300.00"),
            bill_id=bill.id,
        ),
    )
    assert payment.kind == PaymentKind.vendor_payment

    ap_after = await ap_aging(db, entity_id=entity_id, as_of=date(2026, 5, 21))
    assert ap_after.total_balance_due == Decimal("0.00")
    assert ap_after.rows == []


async def test_business_statements_derive_from_posted_ledger(seeded, db):
    entity_id = uuid.UUID(seeded["business_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)

    customer = await create_customer(db, entity_id=entity_id, payload=CustomerCreate(name="Acme"))
    invoice = await create_invoice(
        db,
        entity_id=entity_id,
        payload=InvoiceCreate(
            customer_id=customer.id,
            number="INV-002",
            invoice_date=date(2026, 5, 1),
            due_date=date(2026, 5, 15),
            lines=[{"description": "Services", "quantity": "1", "unit_price": "1000.00", "revenue_account_id": accounts["4200"].id}],
        ),
    )
    await post_invoice(db, invoice, user_id=user_id, confirmed=True)

    vendor = await create_vendor(db, entity_id=entity_id, payload=VendorCreate(name="Landlord"))
    bill = await create_bill(
        db,
        entity_id=entity_id,
        payload=BillCreate(
            vendor_id=vendor.id,
            number="BILL-002",
            bill_date=date(2026, 5, 2),
            due_date=date(2026, 5, 20),
            lines=[{"description": "Rent", "quantity": "1", "unit_price": "300.00", "expense_account_id": accounts["6100"].id}],
        ),
    )
    await post_bill(db, bill, user_id=user_id, confirmed=True)

    await record_payment(
        db,
        entity_id=entity_id,
        user_id=user_id,
        payload=PaymentCreate(
            confirmed=True,
            kind=PaymentKind.customer_receipt,
            payment_date=date(2026, 5, 3),
            amount=Decimal("1000.00"),
            invoice_id=invoice.id,
        ),
    )

    is_report = await income_statement(db, entity_id=entity_id, date_from=date(2026, 5, 1), date_to=date(2026, 5, 31))
    bs = await balance_sheet(db, entity_id=entity_id, as_of=date(2026, 5, 31))
    cf = await cash_flow_statement(db, entity_id=entity_id, date_from=date(2026, 5, 1), date_to=date(2026, 5, 31))
    dashboard = await business_dashboard(db, entity_id=entity_id, as_of=date(2026, 5, 31))

    assert is_report.total_income == Decimal("1000.00")
    assert is_report.total_expenses == Decimal("300.00")
    assert is_report.net_income == Decimal("700.00")
    assert bs.is_balanced is True
    assert bs.total_assets == Decimal("1000.00")
    assert bs.total_liabilities == Decimal("300.00")
    assert bs.total_equity == Decimal("700.00")
    assert cf.total_cash_change == Decimal("1000.00")
    assert dashboard.cash_balance == Decimal("1000.00")
    assert dashboard.accounts_receivable == Decimal("0.00")
    assert dashboard.accounts_payable == Decimal("300.00")
    assert dashboard.monthly_net_income == Decimal("700.00")


async def test_business_advanced_reports_and_explanations(seeded, db):
    entity_id = uuid.UUID(seeded["business_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)

    customer = await create_customer(db, entity_id=entity_id, payload=CustomerCreate(name="Northwind"))
    invoice = await create_invoice(
        db,
        entity_id=entity_id,
        payload=InvoiceCreate(
            customer_id=customer.id,
            number="INV-003",
            invoice_date=date(2026, 5, 1),
            due_date=date(2026, 5, 20),
            lines=[{"description": "Product sale", "quantity": "1", "unit_price": "1200.00", "revenue_account_id": accounts["4100"].id}],
        ),
    )
    await post_invoice(db, invoice, user_id=user_id, confirmed=True)

    vendor = await create_vendor(db, entity_id=entity_id, payload=VendorCreate(name="Supplier Co"))
    cogs_bill = await create_bill(
        db,
        entity_id=entity_id,
        payload=BillCreate(
            vendor_id=vendor.id,
            number="BILL-COGS-001",
            bill_date=date(2026, 5, 2),
            due_date=date(2026, 5, 10),
            lines=[{"description": "Inventory cost", "quantity": "1", "unit_price": "500.00", "expense_account_id": accounts["5100"].id}],
        ),
    )
    await post_bill(db, cogs_bill, user_id=user_id, confirmed=True)

    overhead_vendor = await create_vendor(db, entity_id=entity_id, payload=VendorCreate(name="Landlord"))
    overhead_bill = await create_bill(
        db,
        entity_id=entity_id,
        payload=BillCreate(
            vendor_id=overhead_vendor.id,
            number="BILL-RENT-003",
            bill_date=date(2026, 5, 3),
            due_date=date(2026, 5, 25),
            lines=[{"description": "Rent", "quantity": "1", "unit_price": "200.00", "expense_account_id": accounts["6100"].id}],
        ),
    )
    await post_bill(db, overhead_bill, user_id=user_id, confirmed=True)

    revenue = await revenue_by_customer(db, entity_id=entity_id, date_from=date(2026, 5, 1), date_to=date(2026, 5, 31))
    expenses = await expenses_by_vendor(db, entity_id=entity_id, date_from=date(2026, 5, 1), date_to=date(2026, 5, 31))
    gross = await gross_margin_report(db, entity_id=entity_id, date_from=date(2026, 5, 1), date_to=date(2026, 5, 31))
    runway = await runway_report(db, entity_id=entity_id, as_of=date(2026, 5, 31))
    reserve = await tax_reserve_report(db, entity_id=entity_id, as_of=date(2026, 5, 31))
    profitability = await explain_business_profitability(db, entity_id=entity_id, date_from=date(2026, 5, 1), date_to=date(2026, 5, 31))
    cash_risk = await explain_cash_flow_risk(db, entity_id=entity_id, as_of=date(2026, 5, 31))

    assert revenue.total_revenue == Decimal("1200.00")
    assert revenue.rows[0].counterparty_name == "Northwind"
    assert expenses.total_expenses == Decimal("700.00")
    assert gross.revenue == Decimal("1200.00")
    assert gross.cost_of_goods_sold == Decimal("500.00")
    assert gross.gross_profit == Decimal("700.00")
    assert reserve.note
    assert "Net income was 500.00" in profitability.cited_facts
    assert "Runway was" in " ".join(cash_risk.cited_facts)
    assert runway.runway_months == Decimal("0.00")
