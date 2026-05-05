from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Attachment, CandidateStatus, DocumentExtraction, ExtractionCandidate, ExtractionStatus, JournalEntry, SourceTransaction
from app.services import ingestion as ingestion_service


pytestmark = pytest.mark.asyncio


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


async def test_csv_import_creates_source_transactions(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    csv_bytes = (
        "date,amount,merchant,currency,external_ref\n"
        "2026-05-01,12.34,Coffee Shop,USD,tx-1\n"
        "2026-05-02,56.78,Grocery Mart,USD,tx-2\n"
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

    assert result.batch.rows_total == 2
    assert result.batch.rows_imported == 2
    assert len(result.source_transactions) == 2
    assert len(rows) == 2
    assert rows[0].merchant == "Coffee Shop"
    assert rows[1].amount == Decimal("56.78")
