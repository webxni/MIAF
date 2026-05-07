from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.main import app
from app.models import AuditLog, SourceTransaction
from app.schemas.ingestion import ExtractedFinancialItem, ExtractedFinancialQuestion
from app.services import ingestion as ingestion_service
from app.services import ocr
from app.errors import MIAFError

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


async def _login_seeded_owner(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": seeded["user_email"], "password": "change-me-on-first-login"},
    )
    assert response.status_code == 200


async def _enable_openai_document_ai(client: AsyncClient, *, consent: bool = True) -> None:
    response = await client.put(
        "/settings",
        json={
            "ai_provider": "openai",
            "ai_api_key": "sk-test-openai-document-1234",
            "openai_document_ai_enabled": True,
            "openai_document_ai_consent_granted": consent,
            "openai_vision_model": "gpt-4o-mini",
            "openai_pdf_model": "gpt-4o-mini",
            "openai_transcription_model": "gpt-4o-mini-transcribe",
        },
    )
    assert response.status_code == 200


def _openai_item(
    *,
    source_type: str,
    method: str,
    amount: str = "14.25",
    date: str = "2026-05-05",
    merchant: str = "Corner Cafe",
) -> ExtractedFinancialItem:
    return ExtractedFinancialItem(
        source_type=source_type,
        detected_document_type="receipt",
        date=date,
        amount=amount,
        currency="USD",
        merchant=merchant,
        description=f"{merchant} extracted by OpenAI",
        candidate_entity_type="personal",
        confidence=Decimal("0.9300"),
        confidence_level="high",
        missing_fields=[],
        questions=[],
        raw_text_reference=f"{merchant}\n{date}\nTotal {amount}",
        file_id=None,
        model_used="gpt-4o-mini",
        extraction_method=method,  # type: ignore[arg-type]
    )


async def test_image_extraction_falls_back_local_when_disabled(client: AsyncClient, seeded: dict, monkeypatch) -> None:
    await _login_seeded_owner(client, seeded)
    monkeypatch.setattr(ocr, "extract_text_from_image", lambda data, *, langs="eng+spa": ("Blurry receipt", 10.0))
    monkeypatch.setattr(
        ingestion_service,
        "openai_extract_image",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("OpenAI should not be called")),
    )

    response = await client.post(
        "/documents/upload",
        data={"entity_id": seeded["personal_entity_id"]},
        files={"file": ("receipt.png", b"\x89PNG...", "image/png")},
    )

    assert response.status_code == 201
    item = response.json()["stored_document"]["extracted_items"][0]
    assert item["extraction_method"] == "local_ocr"


async def test_image_extraction_calls_openai_when_enabled_and_low_confidence(
    client: AsyncClient, seeded: dict, monkeypatch
) -> None:
    await _login_seeded_owner(client, seeded)
    await _enable_openai_document_ai(client)
    monkeypatch.setattr(ocr, "extract_text_from_image", lambda data, *, langs="eng+spa": ("Blurry receipt", 10.0))
    monkeypatch.setattr(
        ingestion_service,
        "openai_extract_image",
        lambda *args, **kwargs: ("Corner Cafe\n2026-05-05\nTotal 14.25", _openai_item(source_type="image", method="openai_vision")),
    )

    response = await client.post(
        "/documents/upload",
        data={"entity_id": seeded["personal_entity_id"]},
        files={"file": ("receipt.png", b"\x89PNG...", "image/png")},
    )

    assert response.status_code == 201
    item = response.json()["stored_document"]["extracted_items"][0]
    assert item["extraction_method"] == "openai_vision"
    assert item["model_used"] == "gpt-4o-mini"


async def test_pdf_empty_text_triggers_openai_when_enabled(client: AsyncClient, seeded: dict, monkeypatch) -> None:
    await _login_seeded_owner(client, seeded)
    await _enable_openai_document_ai(client)
    monkeypatch.setattr(ingestion_service, "_printable_pdf_text", lambda data: "")
    monkeypatch.setattr(
        ingestion_service,
        "openai_extract_pdf",
        lambda *args, **kwargs: ("Vendor Invoice\n2026-05-05\nTotal 49.99", _openai_item(source_type="pdf", method="openai_pdf", amount="49.99", merchant="Vendor Invoice")),
    )

    response = await client.post(
        "/documents/upload",
        data={"entity_id": seeded["personal_entity_id"]},
        files={"file": ("invoice.pdf", b"%PDF-1.4\n...", "application/pdf")},
    )

    assert response.status_code == 201
    item = response.json()["stored_document"]["extracted_items"][0]
    assert item["extraction_method"] == "openai_pdf"


async def test_audio_transcription_calls_openai_when_enabled(client: AsyncClient, seeded: dict, monkeypatch) -> None:
    await _login_seeded_owner(client, seeded)
    await _enable_openai_document_ai(client)
    monkeypatch.setattr(ingestion_service, "openai_transcribe_audio", lambda *args, **kwargs: "I spent 25 dollars on gas today")
    monkeypatch.setattr(
        ingestion_service,
        "openai_extract_from_text",
        lambda *args, **kwargs: ("I spent 25 dollars on gas today", _openai_item(source_type="text", method="openai_text", amount="25.00", merchant="Gas Station")),
    )

    response = await client.post(
        "/documents/upload",
        data={"entity_id": seeded["personal_entity_id"]},
        files={"file": ("note.ogg", b"OggS...", "audio/ogg")},
    )

    assert response.status_code == 201
    item = response.json()["stored_document"]["extracted_items"][0]
    assert item["extraction_method"] == "openai_audio"
    assert "gpt-4o-mini-transcribe" in (item["model_used"] or "")


async def test_user_consent_required_for_openai_processing(client: AsyncClient, seeded: dict, monkeypatch) -> None:
    await _login_seeded_owner(client, seeded)
    await _enable_openai_document_ai(client, consent=False)
    monkeypatch.setattr(ocr, "extract_text_from_image", lambda data, *, langs="eng+spa": ("Blurry receipt", 10.0))
    monkeypatch.setattr(
        ingestion_service,
        "openai_extract_image",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("OpenAI should not be called without consent")),
    )

    response = await client.post(
        "/documents/upload",
        data={"entity_id": seeded["personal_entity_id"]},
        files={"file": ("receipt.png", b"\x89PNG...", "image/png")},
    )

    assert response.status_code == 201
    item = response.json()["stored_document"]["extracted_items"][0]
    assert item["extraction_method"] == "local_ocr"


async def test_malformed_openai_json_becomes_review_item_not_crash(client: AsyncClient, seeded: dict, monkeypatch) -> None:
    await _login_seeded_owner(client, seeded)
    await _enable_openai_document_ai(client)
    monkeypatch.setattr(ingestion_service, "_printable_pdf_text", lambda data: "")
    monkeypatch.setattr(
        ingestion_service,
        "openai_extract_pdf",
        lambda *args, **kwargs: (_ for _ in ()).throw(MIAFError("bad json", code="openai_invalid_json")),
    )

    response = await client.post(
        "/documents/upload",
        data={"entity_id": seeded["personal_entity_id"]},
        files={"file": ("scan.pdf", b"%PDF-1.4\n...", "application/pdf")},
    )

    assert response.status_code == 201
    item = response.json()["stored_document"]["extracted_items"][0]
    assert item["confidence_level"] == "low"
    assert response.json()["stored_document"]["extraction"]["status"] == "needs_review"


async def test_csv_local_parser_does_not_call_openai_when_headers_are_clear(seeded, db, monkeypatch) -> None:
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    monkeypatch.setattr(
        ingestion_service,
        "openai_map_csv_columns",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("OpenAI should not be called")),
    )

    result = await ingestion_service.import_csv_transactions(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="bank.csv",
        content_type="text/csv",
        data=b"date,amount,merchant\n2026-05-01,-12.34,Shell\n",
    )

    assert result.batch.rows_imported == 1


async def test_csv_openai_mapping_suggests_columns_but_local_code_parses_rows(
    client: AsyncClient, seeded: dict, db, monkeypatch
) -> None:
    await _login_seeded_owner(client, seeded)
    await _enable_openai_document_ai(client)
    monkeypatch.setattr(
        ingestion_service,
        "openai_map_csv_columns",
        lambda *args, **kwargs: SimpleNamespace(
            date_column="posted_on",
            amount_column=None,
            debit_column="debit_amount",
            credit_column=None,
            description_column="details",
            merchant_column=None,
            category_column=None,
            account_column=None,
        ),
    )

    result = await ingestion_service.import_csv_transactions(
        db,
        tenant_id=uuid.UUID(seeded["tenant_id"]),
        entity_id=uuid.UUID(seeded["personal_entity_id"]),
        user_id=uuid.UUID(seeded["user_id"]),
        filename="bank.csv",
        content_type="text/csv",
        data=b"posted_on,debit_amount,details\n2026-05-01,12.34,Shell fuel\n",
    )

    tx = (
        await db.execute(select(SourceTransaction).where(SourceTransaction.entity_id == uuid.UUID(seeded["personal_entity_id"])))
    ).scalar_one()
    assert result.batch.rows_imported == 1
    assert tx.amount == Decimal("-12.34")


async def test_openai_extraction_audit_logs_created(client: AsyncClient, seeded: dict, db, monkeypatch) -> None:
    await _login_seeded_owner(client, seeded)
    await _enable_openai_document_ai(client)
    monkeypatch.setattr(ocr, "extract_text_from_image", lambda data, *, langs="eng+spa": ("Blurry receipt", 10.0))
    monkeypatch.setattr(
        ingestion_service,
        "openai_extract_image",
        lambda *args, **kwargs: ("Corner Cafe\n2026-05-05\nTotal 14.25", _openai_item(source_type="image", method="openai_vision")),
    )

    response = await client.post(
        "/documents/upload",
        data={"entity_id": seeded["personal_entity_id"]},
        files={"file": ("receipt.png", b"\x89PNG...", "image/png")},
    )

    assert response.status_code == 201
    actions = (
        await db.execute(
            select(AuditLog.action).where(AuditLog.object_type == "document").order_by(AuditLog.created_at)
        )
    ).scalars().all()
    assert "document_openai_extraction_started" in actions
    assert "document_openai_extraction_completed" in actions
