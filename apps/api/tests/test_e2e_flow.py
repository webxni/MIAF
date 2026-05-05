from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import Response
from sqlalchemy import select

from app.api.auth import login
from app.api.deps import RequestContext
from app.models import Account, Alert, AuditLog, GeneratedReport, HeartbeatType, JournalEntry, JournalEntryStatus
from app.schemas.auth import LoginRequest
from app.schemas.business import BillCreate, CustomerCreate, InvoiceCreate, PaymentCreate, TaxReserveCreate, VendorCreate
from app.schemas.journal import JournalEntryCreate, JournalLineIn
from app.schemas.personal import BudgetCreate
from app.services import ingestion as ingestion_service
from app.services.business import (
    balance_sheet,
    business_dashboard,
    create_bill,
    create_customer,
    create_invoice,
    create_tax_reserve,
    create_vendor,
    income_statement,
    post_bill,
    post_invoice,
    record_payment,
)
from app.services.heartbeat import run_heartbeat
from app.services.ingestion import approve_candidate, import_csv_transactions, ingest_receipt
from app.services.journal import create_draft, get_entry_scoped, post_entry
from app.services.personal import budget_actuals, create_budget, personal_dashboard

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _mock_storage(monkeypatch):
    async def fake_put_object(client, bucket, key, data, content_type):
        return None

    async def fake_presigned_get_url(client, bucket, key):
        return f"https://example.test/{bucket}/{key}"

    monkeypatch.setattr(ingestion_service, "_put_object", fake_put_object)
    monkeypatch.setattr(ingestion_service, "_presigned_get_url", fake_presigned_get_url)


async def _accounts(db, entity_id: uuid.UUID) -> dict[str, Account]:
    rows = (await db.execute(select(Account).where(Account.entity_id == entity_id))).scalars().all()
    return {row.code: row for row in rows}


async def test_end_to_end_demo_flow(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])
    personal_entity_id = uuid.UUID(seeded["personal_entity_id"])
    business_entity_id = uuid.UUID(seeded["business_entity_id"])
    personal_accounts = await _accounts(db, personal_entity_id)
    business_accounts = await _accounts(db, business_entity_id)

    response = Response()
    user = await login(
        LoginRequest(email=seeded["user_email"], password="change-me-on-first-login"),
        response,
        db,
        RequestContext(ip="127.0.0.1", user_agent="pytest-e2e"),
    )
    assert user.email == seeded["user_email"]

    budget = await create_budget(
        db,
        entity_id=personal_entity_id,
        payload=BudgetCreate(
            name="May 2026",
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
            lines=[{"account_id": personal_accounts["5200"].id, "planned_amount": "300.00"}],
        ),
    )

    csv_bytes = (
        "date,amount,merchant,currency,external_ref\n"
        "2026-05-01,75.00,Payroll Deposit,USD,tx-1\n"
    ).encode("utf-8")
    csv_result = await import_csv_transactions(
        db,
        tenant_id=tenant_id,
        entity_id=personal_entity_id,
        user_id=user_id,
        filename="bank.csv",
        content_type="text/csv",
        data=csv_bytes,
    )
    assert csv_result.batch.rows_imported == 1

    receipt = b"Corner Cafe\n2026-05-05\nTotal 14.25\n"
    ingested = await ingest_receipt(
        db,
        tenant_id=tenant_id,
        entity_id=personal_entity_id,
        user_id=user_id,
        filename="receipt.txt",
        content_type="text/plain",
        data=receipt,
    )
    approved = await approve_candidate(
        db,
        entity_id=personal_entity_id,
        candidate_id=ingested.candidate.id,
        user_id=user_id,
    )
    approved_entry = await get_entry_scoped(db, entity_id=personal_entity_id, entry_id=approved.journal_entry_id)
    assert approved_entry is not None and approved_entry.status == JournalEntryStatus.draft
    await post_entry(db, approved_entry, posted_by_id=user_id)

    customer = await create_customer(db, entity_id=business_entity_id, payload=CustomerCreate(name="Acme"))
    invoice = await create_invoice(
        db,
        entity_id=business_entity_id,
        payload=InvoiceCreate(
            customer_id=customer.id,
            number="INV-E2E-001",
            invoice_date=date(2026, 5, 6),
            due_date=date(2026, 5, 20),
            lines=[{"description": "Consulting", "quantity": "1", "unit_price": "1000.00", "revenue_account_id": business_accounts["4200"].id}],
        ),
    )
    await post_invoice(db, invoice, user_id=user_id, confirmed=True)
    await record_payment(
        db,
        entity_id=business_entity_id,
        user_id=user_id,
        payload=PaymentCreate(
            confirmed=True,
            kind="customer_receipt",
            payment_date=date(2026, 5, 7),
            amount=Decimal("1000.00"),
            invoice_id=invoice.id,
        ),
    )

    vendor = await create_vendor(db, entity_id=business_entity_id, payload=VendorCreate(name="ISP"))
    bill = await create_bill(
        db,
        entity_id=business_entity_id,
        payload=BillCreate(
            vendor_id=vendor.id,
            number="BILL-E2E-001",
            bill_date=date(2026, 5, 8),
            due_date=date(2026, 5, 18),
            lines=[{"description": "Internet", "quantity": "1", "unit_price": "150.00", "expense_account_id": business_accounts["6300"].id}],
        ),
    )
    await post_bill(db, bill, user_id=user_id, confirmed=True)

    business_draw = await create_draft(
        db,
        entity_id=business_entity_id,
        user_id=user_id,
        payload=JournalEntryCreate(
            entry_date=date(2026, 5, 9),
            memo="Owner draw to personal",
            lines=[
                JournalLineIn(account_id=business_accounts["3300"].id, debit=Decimal("200.00"), credit=Decimal("0")),
                JournalLineIn(account_id=business_accounts["1110"].id, debit=Decimal("0"), credit=Decimal("200.00")),
            ],
        ),
    )
    await post_entry(db, business_draw, posted_by_id=user_id)

    personal_draw = await create_draft(
        db,
        entity_id=personal_entity_id,
        user_id=user_id,
        payload=JournalEntryCreate(
            entry_date=date(2026, 5, 9),
            memo="Owner draw received",
            linked_entry_id=business_draw.id,
            lines=[
                JournalLineIn(account_id=personal_accounts["1110"].id, debit=Decimal("200.00"), credit=Decimal("0")),
                JournalLineIn(account_id=personal_accounts["4200"].id, debit=Decimal("0"), credit=Decimal("200.00")),
            ],
        ),
    )
    await post_entry(db, personal_draw, posted_by_id=user_id)

    await create_tax_reserve(
        db,
        entity_id=business_entity_id,
        payload=TaxReserveCreate(
            as_of=date(2026, 5, 31),
            estimated_tax=Decimal("500.00"),
            reserved_amount=Decimal("100.00"),
        ),
    )

    personal_actuals = await budget_actuals(db, entity_id=personal_entity_id, budget_id=budget.id)
    business_bs = await balance_sheet(db, entity_id=business_entity_id, as_of=date(2026, 5, 31))
    business_is = await income_statement(db, entity_id=business_entity_id, date_from=date(2026, 5, 1), date_to=date(2026, 5, 31))
    personal_summary = await personal_dashboard(db, entity_id=personal_entity_id, as_of=date(2026, 5, 31))
    business_summary = await business_dashboard(db, entity_id=business_entity_id, as_of=date(2026, 5, 31))

    daily_business = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.daily_business_check,
        as_of=date(2026, 5, 31),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )
    weekly = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.weekly_business_report,
        as_of=date(2026, 5, 31),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )

    alerts = (await db.execute(select(Alert))).scalars().all()
    reports = (await db.execute(select(GeneratedReport))).scalars().all()
    audits = (await db.execute(select(AuditLog))).scalars().all()

    assert personal_actuals.total_actual == Decimal("14.25")
    assert business_bs.is_balanced is True
    assert business_is.net_income == Decimal("850.00")
    assert business_summary.cash_balance == Decimal("800.00")
    assert personal_summary.net_worth == Decimal("185.75")
    assert any(alert.alert_type == "tax_reserve_gap" for alert in daily_business.alerts)
    assert len(weekly.reports) == 1
    assert alerts
    assert reports
    assert audits
