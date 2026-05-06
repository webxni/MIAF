from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import ExtractionCandidate, ExtractionStatus
from app.services import ingestion as ingestion_service
from app.services import ocr


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


def test_is_image_content_type() -> None:
    assert ocr.is_image_content_type("image/png") is True
    assert ocr.is_image_content_type("image/jpeg") is True
    assert ocr.is_image_content_type("image/jpg") is True
    assert ocr.is_image_content_type("image/webp") is True
    assert ocr.is_image_content_type("application/pdf") is False
    assert ocr.is_image_content_type("text/plain") is False


def test_extract_text_from_image_returns_empty_on_invalid_data() -> None:
    text, confidence = ocr.extract_text_from_image(b"not an image")

    assert text == ""
    assert confidence == 0.0


async def test_ingest_pdf_returns_needs_review(seeded, db) -> None:
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])

    result = await ingestion_service.ingest_receipt(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="receipt.pdf",
        content_type="application/pdf",
        data=b"%PDF-1.4\n...",
    )

    candidates = (
        await db.execute(select(ExtractionCandidate).where(ExtractionCandidate.document_extraction_id == result.extraction.id))
    ).scalars().all()

    assert result.candidate is None
    assert result.extraction.status == ExtractionStatus.needs_review
    assert result.extraction.confidence_score == Decimal("0.0000")
    assert result.extraction.extracted_data["reason"] == "pdf_not_supported_yet"
    assert result.extraction.extracted_data["merchant"]["value"] is None
    assert result.extraction.extracted_data["date"]["value"] is None
    assert result.extraction.extracted_data["total"]["value"] is None
    assert candidates == []


async def test_ingest_image_runs_ocr(seeded, db, monkeypatch) -> None:
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])

    monkeypatch.setattr(
        ocr,
        "extract_text_from_image",
        lambda data, *, langs="eng+spa": ("Corner Cafe\n2026-05-05\nTotal 14.25\n", 90.0),
    )

    result = await ingestion_service.ingest_receipt(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="receipt.png",
        content_type="image/png",
        data=b"\x89PNG...",
    )

    assert result.candidate is not None
    assert result.extraction.status == ExtractionStatus.extracted
    assert result.extraction.extracted_data["merchant"]["value"] == "Corner Cafe"
    assert result.extraction.extracted_data["date"]["value"] == "2026-05-05"
    assert result.extraction.extracted_data["total"]["value"] == "14.25"
    assert Decimal(str(result.extraction.extracted_data["total"]["confidence"])) == Decimal("0.8280")
    assert result.candidate.suggested_memo == "Corner Cafe"
    assert result.candidate.suggested_entry["lines"][0]["debit"] == "14.25"
