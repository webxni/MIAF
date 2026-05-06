from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.main import app
from app.models import Account, Attachment, AuditLog, CandidateStatus, DocumentExtraction, ExtractionCandidate, ExtractionStatus, JournalEntry, SourceTransaction
from app.services import ingestion as ingestion_service


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


async def _login_seeded_owner(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": seeded["user_email"], "password": "change-me-on-first-login"},
    )
    assert response.status_code == 200


@pytest.fixture(autouse=True)
def _mock_storage(monkeypatch):
    stored: dict[str, bytes] = {}

    async def fake_put_object(client, bucket, key, data, content_type):
        stored[key] = data

    async def fake_presigned_get_url(client, bucket, key):
        return f"https://example.test/{bucket}/{key}"

    monkeypatch.setattr(ingestion_service, "_put_object", fake_put_object)
    monkeypatch.setattr(ingestion_service, "_presigned_get_url", fake_presigned_get_url)
    return stored


async def test_receipt_upload_extracts_and_suggests_entry(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    receipt = b"Corner Cafe\n2026-05-05\nTotal 14.25\n"

    result = await ingestion_service.ingest_receipt(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="receipt.txt",
        content_type="text/plain",
        data=receipt,
    )

    assert result.attachment.filename == "receipt.txt"
    assert result.extraction.status == ExtractionStatus.extracted
    assert result.extraction.extracted_data["merchant"]["value"] == "Corner Cafe"
    assert result.extraction.extracted_data["total"]["value"] == "14.25"
    assert result.candidate.status == CandidateStatus.suggested
    assert result.candidate.suggested_entry["lines"][0]["debit"] == "14.25"


async def test_candidate_approval_creates_draft_journal_entry_and_keeps_attachment(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    receipt = b"Corner Cafe\n2026-05-05\nTotal 14.25\n"

    ingested = await ingestion_service.ingest_receipt(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="receipt.txt",
        content_type="text/plain",
        data=receipt,
    )
    approved = await ingestion_service.approve_candidate(
        db,
        entity_id=entity_id,
        candidate_id=ingested.candidate.id,
        user_id=user_id,
    )

    candidate = await db.get(ExtractionCandidate, ingested.candidate.id)
    extraction = await db.get(DocumentExtraction, ingested.extraction.id)
    attachment = await db.get(Attachment, ingested.attachment.id)
    entry = await db.get(JournalEntry, approved.journal_entry_id)
    source_tx = await db.get(SourceTransaction, ingested.extraction.source_transaction_id)

    assert candidate is not None and candidate.status == CandidateStatus.approved
    assert extraction is not None and extraction.status == ExtractionStatus.approved
    assert entry is not None and entry.status.value == "draft"
    assert attachment is not None and attachment.journal_entry_id == entry.id
    assert source_tx is not None and source_tx.status.value == "matched"


async def test_csv_import_creates_auto_drafts_for_outflows(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    csv_bytes = (
        "date,amount,merchant,memo,currency,external_ref\n"
        "2026-05-01,-12.34,Shell,gasolina fill-up,USD,tx-1\n"
        "2026-05-02,-56.78,Grocery Mart,weekly grocer run,USD,tx-2\n"
    ).encode("utf-8")

    result = await ingestion_service.import_csv_transactions(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="bank.csv",
        content_type="text/csv",
        data=csv_bytes,
    )

    rows = (
        await db.execute(select(SourceTransaction).where(SourceTransaction.entity_id == entity_id).order_by(SourceTransaction.occurred_at))
    ).scalars().all()
    entries = (
        await db.execute(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.entity_id == entity_id)
            .order_by(JournalEntry.entry_date)
        )
    ).scalars().all()
    accounts = {
        account.id: account
        for account in (
            await db.execute(select(Account).where(Account.entity_id == entity_id))
        ).scalars().all()
    }
    audits = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == entity_id, AuditLog.action == "auto_draft")
            .order_by(AuditLog.created_at)
        )
    ).scalars().all()

    assert result.batch.rows_total == 2
    assert result.batch.rows_imported == 2
    assert result.drafts_created == 2
    assert len(result.source_transactions) == 2
    assert len(rows) == 2
    assert len(entries) == 2
    assert rows[0].merchant == "Shell"
    assert rows[0].status.value == "matched"
    assert rows[1].amount == Decimal("-56.78")

    first_lines = sorted(entries[0].lines, key=lambda line: line.line_no)
    second_lines = sorted(entries[1].lines, key=lambda line: line.line_no)

    assert entries[0].source_transaction_id == rows[0].id
    assert entries[1].source_transaction_id == rows[1].id
    assert first_lines[0].debit == Decimal("12.34")
    assert first_lines[0].credit == Decimal("0.00")
    assert first_lines[1].debit == Decimal("0.00")
    assert first_lines[1].credit == Decimal("12.34")
    assert second_lines[0].debit == Decimal("56.78")
    assert second_lines[1].credit == Decimal("56.78")
    assert accounts[first_lines[0].account_id].code == "5300"
    assert accounts[second_lines[0].account_id].code == "5200"
    assert accounts[first_lines[1].account_id].code == "1110"
    assert accounts[second_lines[1].account_id].code == "1110"
    assert len(audits) == 2
    assert audits[0].after["source_transaction_id"] == str(rows[0].id)
    assert audits[0].after["classifier_reason"] == "keyword:gas"
    assert audits[1].after["source_transaction_id"] == str(rows[1].id)
    assert audits[1].after["classifier_reason"] == "keyword:grocer"


async def test_csv_import_inflow_creates_no_draft(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    csv_bytes = (
        "date,amount,merchant,memo,currency,external_ref\n"
        "2026-05-03,1250.00,Employer,payroll deposit,USD,tx-3\n"
    ).encode("utf-8")

    result = await ingestion_service.import_csv_transactions(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="bank.csv",
        content_type="text/csv",
        data=csv_bytes,
    )

    rows = (await db.execute(select(SourceTransaction).where(SourceTransaction.entity_id == entity_id))).scalars().all()
    entries = (await db.execute(select(JournalEntry).where(JournalEntry.entity_id == entity_id))).scalars().all()

    assert result.batch.rows_imported == 1
    assert result.drafts_created == 0
    assert len(rows) == 1
    assert rows[0].amount == Decimal("1250.00")
    assert rows[0].status.value == "pending"
    assert entries == []


async def test_pending_drafts_endpoint_returns_source_context(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    csv_bytes = (
        "date,amount,merchant,memo,currency,external_ref\n"
        "2026-05-01,-12.34,Shell,gasolina fill-up,USD,tx-1\n"
        "2026-05-02,-56.78,Grocery Mart,weekly grocer run,USD,tx-2\n"
    ).encode("utf-8")

    await ingestion_service.import_csv_transactions(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="bank.csv",
        content_type="text/csv",
        data=csv_bytes,
    )

    response = await client.get(f"/entities/{entity_id}/documents/pending-drafts")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["source"]["merchant"] == "Grocery Mart"
    assert body[0]["source"]["memo"] == "weekly grocer run"
    assert body[0]["source"]["amount"] == "-56.78"
    assert body[0]["source"]["currency"] == "USD"
    assert body[0]["source"]["posted_at"].startswith("2026-05-02T00:00:00")
    assert len(body[0]["lines"]) == 2
    assert body[1]["source"]["merchant"] == "Shell"
