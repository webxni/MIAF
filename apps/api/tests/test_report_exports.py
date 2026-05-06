"""Tests for CSV report exports and report-access audit logging."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.main import app
from app.models import AuditLog

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.pop(get_db, None)


async def _login(client: AsyncClient, seeded: dict) -> None:
    r = await client.post("/auth/login", json={"email": seeded["user_email"], "password": "change-me-on-first-login"})
    assert r.status_code == 200


# ── Trial balance CSV ─────────────────────────────────────────────────────────

async def test_trial_balance_csv_returns_csv_and_audits(client, seeded, db):
    await _login(client, seeded)
    entity_id = seeded["business_entity_id"]

    r = await client.get(f"/entities/{entity_id}/trial-balance/export.csv?as_of={date.today()}")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    # Header row must be present
    assert lines[0] == "Account Code,Account Name,Type,Debit,Credit"
    # At least the TOTAL row
    assert any("TOTAL" in line for line in lines)

    audit = (
        await db.execute(select(AuditLog).where(AuditLog.action == "export", AuditLog.object_type == "trial_balance"))
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.after["format"] == "csv"


async def test_trial_balance_json_audits_report_viewed(client, seeded, db):
    await _login(client, seeded)
    entity_id = seeded["business_entity_id"]

    r = await client.get(f"/entities/{entity_id}/trial-balance?as_of={date.today()}")
    assert r.status_code == 200

    audit = (
        await db.execute(select(AuditLog).where(AuditLog.action == "report_viewed", AuditLog.object_type == "trial_balance"))
    ).scalar_one_or_none()
    assert audit is not None


# ── Ledger CSV ────────────────────────────────────────────────────────────────

async def test_ledger_csv_requires_auth(client, seeded):
    entity_id = seeded["business_entity_id"]
    r = await client.get(f"/entities/{entity_id}/ledger/export.csv?account_id={uuid.uuid4()}")
    assert r.status_code in (401, 403)


# ── Balance sheet CSV ─────────────────────────────────────────────────────────

async def test_balance_sheet_csv_returns_sections(client, seeded, db):
    await _login(client, seeded)
    entity_id = seeded["business_entity_id"]

    r = await client.get(f"/entities/{entity_id}/business/reports/balance-sheet/export.csv?as_of={date.today()}")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "Section,Account Code,Account Name,Amount"
    sections = {line.split(",")[0] for line in lines[1:]}
    assert "Summary" in sections

    audit = (
        await db.execute(select(AuditLog).where(AuditLog.action == "export", AuditLog.object_type == "balance_sheet"))
    ).scalar_one_or_none()
    assert audit is not None


async def test_balance_sheet_json_audits_report_viewed(client, seeded, db):
    await _login(client, seeded)
    entity_id = seeded["business_entity_id"]

    r = await client.get(f"/entities/{entity_id}/business/reports/balance-sheet?as_of={date.today()}")
    assert r.status_code == 200

    audit = (
        await db.execute(select(AuditLog).where(AuditLog.action == "report_viewed", AuditLog.object_type == "balance_sheet"))
    ).scalar_one_or_none()
    assert audit is not None


# ── AR/AP aging CSV ───────────────────────────────────────────────────────────

async def test_ar_aging_csv_returns_correct_headers(client, seeded, db):
    await _login(client, seeded)
    entity_id = seeded["business_entity_id"]

    r = await client.get(f"/entities/{entity_id}/business/reports/ar-aging/export.csv?as_of={date.today()}")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    header = r.text.strip().splitlines()[0]
    assert "Customer" in header
    assert "Balance Due" in header


async def test_ap_aging_json_audits_report_viewed(client, seeded, db):
    await _login(client, seeded)
    entity_id = seeded["business_entity_id"]

    r = await client.get(f"/entities/{entity_id}/business/reports/ap-aging?as_of={date.today()}")
    assert r.status_code == 200

    audit = (
        await db.execute(select(AuditLog).where(AuditLog.action == "report_viewed", AuditLog.object_type == "ap_aging"))
    ).scalar_one_or_none()
    assert audit is not None


# ── Income statement CSV ──────────────────────────────────────────────────────

async def test_income_statement_csv_returns_revenue_and_expenses(client, seeded, db):
    await _login(client, seeded)
    entity_id = seeded["business_entity_id"]
    today = date.today()
    date_from = today.replace(day=1)

    r = await client.get(f"/entities/{entity_id}/business/reports/income-statement/export.csv?date_from={date_from}&date_to={today}")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "Section,Account Code,Account Name,Amount"
    assert any("Summary" in line for line in lines)


# ── Personal net-worth CSV ────────────────────────────────────────────────────

async def test_net_worth_csv_returns_summary_rows(client, seeded, db):
    await _login(client, seeded)
    entity_id = seeded["personal_entity_id"]

    r = await client.get(f"/entities/{entity_id}/personal/reports/net-worth/export.csv?as_of={date.today()}")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "Metric,Amount"
    metrics = {line.split(",")[0] for line in lines[1:]}
    assert "Net Worth" in metrics


async def test_net_worth_json_audits_report_viewed(client, seeded, db):
    await _login(client, seeded)
    entity_id = seeded["personal_entity_id"]

    r = await client.get(f"/entities/{entity_id}/personal/reports/net-worth?as_of={date.today()}")
    assert r.status_code == 200

    audit = (
        await db.execute(select(AuditLog).where(AuditLog.action == "report_viewed", AuditLog.object_type == "net_worth"))
    ).scalar_one_or_none()
    assert audit is not None


# ── Export requires auth ──────────────────────────────────────────────────────

async def test_csv_exports_require_auth(client, seeded):
    entity_id = seeded["business_entity_id"]
    today = date.today()
    date_from = today.replace(day=1)

    endpoints = [
        f"/entities/{entity_id}/trial-balance/export.csv?as_of={today}",
        f"/entities/{entity_id}/business/reports/balance-sheet/export.csv?as_of={today}",
        f"/entities/{entity_id}/business/reports/ar-aging/export.csv?as_of={today}",
        f"/entities/{entity_id}/business/reports/income-statement/export.csv?date_from={date_from}&date_to={today}",
        f"/entities/{entity_id}/personal/reports/net-worth/export.csv?as_of={today}",
    ]
    for url in endpoints:
        r = await client.get(url)
        assert r.status_code in (401, 403), f"Expected auth failure for {url}, got {r.status_code}"
