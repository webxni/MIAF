from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import (
    Account,
    Attachment,
    AlertSeverity,
    DocumentExtraction,
    ExtractionStatus,
    GeneratedReport,
    HeartbeatRun,
    HeartbeatType,
    NetWorthSnapshot,
    ReportKind,
)
from app.schemas.business import BillCreate, TaxReserveCreate, VendorCreate
from app.schemas.journal import JournalEntryCreate, JournalLineIn
from app.schemas.personal import BudgetCreate
from app.services.business import create_bill, create_tax_reserve, create_vendor, post_bill
from app.services.heartbeat import run_default_scheduled_heartbeats, run_heartbeat
from app.services.journal import create_draft, post_entry
from app.services.personal import create_budget

pytestmark = pytest.mark.asyncio


async def _accounts(db, entity_id: uuid.UUID) -> dict[str, Account]:
    rows = (await db.execute(select(Account).where(Account.entity_id == entity_id))).scalars().all()
    return {row.code: row for row in rows}


async def _post(db, entity_id: uuid.UUID, user_id: uuid.UUID, payload: JournalEntryCreate) -> None:
    entry = await create_draft(db, entity_id=entity_id, user_id=user_id, payload=payload)
    await post_entry(db, entry, posted_by_id=user_id)


async def test_tax_reserve_check_creates_gap_alert(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["business_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])

    await create_tax_reserve(
        db,
        entity_id=entity_id,
        payload=TaxReserveCreate(
            as_of=date(2026, 5, 6),
            estimated_tax=Decimal("500.00"),
            reserved_amount=Decimal("100.00"),
        ),
    )

    result = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.tax_reserve_check,
        as_of=date(2026, 5, 6),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )

    assert len(result.alerts) == 1
    assert result.alerts[0].alert_type == "tax_reserve_gap"


async def test_cash_runway_check_creates_critical_alert(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["business_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)

    vendor = await create_vendor(db, entity_id=entity_id, payload=VendorCreate(name="Landlord"))
    bill = await create_bill(
        db,
        entity_id=entity_id,
        payload=BillCreate(
            vendor_id=vendor.id,
            number="BILL-HB-EXTRA-001",
            bill_date=date(2026, 5, 1),
            due_date=date(2026, 5, 2),
            lines=[
                {
                    "description": "Rent",
                    "quantity": "1",
                    "unit_price": "800.00",
                    "expense_account_id": accounts["6100"].id,
                }
            ],
        ),
    )
    await post_bill(db, bill, user_id=user_id, confirmed=True)

    result = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.cash_runway_check,
        as_of=date(2026, 5, 6),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )

    assert len(result.alerts) == 1
    assert result.alerts[0].alert_type == "cash_runway_low"
    assert result.alerts[0].severity == AlertSeverity.critical


async def test_budget_overspend_check_creates_line_alert(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)

    await create_budget(
        db,
        entity_id=entity_id,
        payload=BudgetCreate(
            name="May 2026",
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
            lines=[{"account_id": accounts["5200"].id, "planned_amount": "500.00"}],
        ),
    )
    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 10),
            memo="Groceries",
            lines=[
                JournalLineIn(account_id=accounts["5200"].id, debit=Decimal("550.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("0"), credit=Decimal("550.00")),
            ],
        ),
    )

    result = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.budget_overspend_check,
        as_of=date(2026, 5, 15),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )

    assert any(alert.alert_type == "budget_overspend" for alert in result.alerts)


async def test_ar_ap_aging_check_noop_without_91_plus_balances(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])

    result = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.ar_ap_aging_check,
        as_of=date(2026, 5, 6),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )

    assert result.alerts == []


async def test_weekly_personal_report_creates_generated_report(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])

    result = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.weekly_personal_report,
        as_of=date(2026, 5, 10),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )

    report = (
        await db.execute(
            select(GeneratedReport).where(GeneratedReport.heartbeat_run_id == result.run.id)
        )
    ).scalar_one()
    assert report.report_kind == ReportKind.weekly_personal_report
    assert len(result.reports) == 1


async def test_monthly_personal_close_creates_snapshot(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])

    result = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.monthly_personal_close,
        as_of=date(2026, 5, 1),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )

    snapshot = (
        await db.execute(
            select(NetWorthSnapshot).where(
                NetWorthSnapshot.entity_id == entity_id,
                NetWorthSnapshot.as_of == date(2026, 5, 1),
            )
        )
    ).scalar_one()
    assert snapshot is not None
    assert result.alerts == []


async def test_monthly_business_close_completes(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])

    result = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.monthly_business_close,
        as_of=date(2026, 5, 1),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )

    assert result.run.status.value == "completed"


async def test_daily_personal_heartbeat_flags_documents_needing_review(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])

    attachment = Attachment(
        tenant_id=tenant_id,
        entity_id=entity_id,
        filename="receipt.txt",
        content_type="text/plain",
        size_bytes=24,
        sha256="a" * 64,
        storage_key="test/receipt.txt",
        uploaded_by_id=user_id,
    )
    db.add(attachment)
    await db.flush()

    extraction = DocumentExtraction(
        tenant_id=tenant_id,
        entity_id=entity_id,
        attachment_id=attachment.id,
        extraction_kind="receipt",
        status=ExtractionStatus.needs_review,
        extracted_data={
            "items": [
                {
                    "source_type": "text",
                    "detected_document_type": "receipt",
                    "candidate_entity_type": "unknown",
                    "confidence": "0.4000",
                    "confidence_level": "low",
                    "questions": [
                        {
                            "code": "personal_business_ambiguous",
                            "question": "Is this personal or business?",
                            "status": "open",
                        }
                    ],
                }
            ]
        },
        confidence_score=Decimal("0.4000"),
        duplicate_detected=True,
    )
    db.add(extraction)
    await db.flush()

    result = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.daily_personal_check,
        as_of=date(2026, 5, 6),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )

    alert_types = {alert.alert_type for alert in result.alerts}
    assert "documents_need_review" in alert_types
    assert "duplicate_documents_detected" in alert_types
    assert "document_questions_open" in alert_types
    assert "low_confidence_documents" in alert_types


async def test_default_scheduler_includes_extra_monday_heartbeats(seeded, db):
    runs = await run_default_scheduled_heartbeats(db, as_of=date(2026, 5, 4))

    types = {run.heartbeat_type for run in runs}
    assert HeartbeatType.daily_personal_check in types
    assert HeartbeatType.daily_business_check in types
    assert HeartbeatType.weekly_business_report in types
    assert HeartbeatType.tax_reserve_check in types
    assert HeartbeatType.cash_runway_check in types
    assert HeartbeatType.budget_overspend_check in types
    assert HeartbeatType.ar_ap_aging_check in types

    stored = (await db.execute(select(HeartbeatRun))).scalars().all()
    assert any(run.heartbeat_type == HeartbeatType.ar_ap_aging_check for run in stored)
