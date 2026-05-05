from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import AlertSeverity, AuditLog, HeartbeatType, ReportKind
from app.schemas.business import BillCreate, TaxReserveCreate, VendorCreate
from app.schemas.personal import DebtCreate
from app.services.business import create_bill, create_tax_reserve, create_vendor, post_bill
from app.services.heartbeat import run_default_scheduled_heartbeats, run_heartbeat
from app.services.personal import create_debt

pytestmark = pytest.mark.asyncio


async def _business_accounts(db, entity_id):
    from sqlalchemy import select

    from app.models import Account

    rows = (await db.execute(select(Account).where(Account.entity_id == entity_id))).scalars().all()
    return {row.code: row for row in rows}


async def test_daily_personal_heartbeat_creates_due_soon_alert(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    tenant_id = uuid.UUID(seeded["tenant_id"])

    await create_debt(
        db,
        entity_id=entity_id,
        payload=DebtCreate(
            confirmed=True,
            name="Visa",
            kind="credit_card",
            current_balance="250.00",
            next_due_date=date(2026, 5, 7),
        ),
    )

    result = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.daily_personal_check,
        as_of=date(2026, 5, 5),
        trigger_source="manual",
        initiated_by_user_id=uuid.UUID(seeded["user_id"]),
    )

    assert result.run.summary["alerts_created"] >= 1
    assert any(alert.alert_type == "debt_due_soon" for alert in result.alerts)


async def test_daily_business_heartbeat_creates_runway_and_overdue_alerts(seeded, db):
    entity_id = uuid.UUID(seeded["business_entity_id"])
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _business_accounts(db, entity_id)

    vendor = await create_vendor(db, entity_id=entity_id, payload=VendorCreate(name="Landlord"))
    bill = await create_bill(
        db,
        entity_id=entity_id,
        payload=BillCreate(
            vendor_id=vendor.id,
            number="BILL-HB-001",
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
    await create_tax_reserve(
        db,
        entity_id=entity_id,
        payload=TaxReserveCreate(
            as_of=date(2026, 5, 5),
            estimated_tax=Decimal("500.00"),
            reserved_amount=Decimal("100.00"),
        ),
    )

    result = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.daily_business_check,
        as_of=date(2026, 5, 5),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )

    types = {alert.alert_type for alert in result.alerts}
    assert "cash_runway_low" in types
    assert "overdue_bills" in types
    assert "tax_reserve_gap" in types
    assert any(alert.severity == AlertSeverity.critical for alert in result.alerts)


async def test_weekly_business_report_is_generated(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    result = await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.weekly_business_report,
        as_of=date(2026, 5, 5),
        trigger_source="manual",
        initiated_by_user_id=uuid.UUID(seeded["user_id"]),
    )

    assert len(result.reports) == 1
    assert result.reports[0].report_kind == ReportKind.weekly_business_report
    assert "Weekly Business Report" in result.reports[0].body


async def test_default_scheduled_heartbeats_include_weekly_report_on_monday(seeded, db):
    runs = await run_default_scheduled_heartbeats(db, as_of=date(2026, 5, 4))
    types = [run.heartbeat_type for run in runs]
    assert HeartbeatType.daily_personal_check in types
    assert HeartbeatType.daily_business_check in types
    assert HeartbeatType.weekly_business_report in types
    audits = (await db.execute(select(AuditLog).where(AuditLog.object_type == "heartbeat"))).scalars().all()
    assert audits
