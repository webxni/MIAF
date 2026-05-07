from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.main import app
from app.models import AuditLog, UserSettings
from app.services.crypto import decrypt_secret, encrypt_secret

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


async def test_settings_get_auto_creates_row(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)

    response = await client.get("/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["base_currency"] == "USD"
    assert body["fiscal_year_start_month"] == 1
    assert body["ai_api_key_present"] is False
    assert body["ai_api_key_hint"] is None
    assert body["openai_document_ai_enabled"] is False
    assert body["openai_document_ai_consent_granted"] is False

    row = (
        await db.execute(
            select(UserSettings).where(UserSettings.user_id == uuid.UUID(seeded["user_id"]))
        )
    ).scalar_one_or_none()
    assert row is not None
    assert row.tenant_id == uuid.UUID(seeded["tenant_id"])


async def test_settings_put_updates_fields_and_persists(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)

    response = await client.put(
        "/settings",
        json={
            "jurisdiction": "US-CA",
            "base_currency": "mxn",
            "fiscal_year_start_month": 4,
            "ai_provider": "openai",
            "ai_model": "gpt-4.1-mini",
            "openai_document_ai_enabled": True,
            "openai_document_ai_consent_granted": True,
            "openai_vision_model": "gpt-4o-mini",
            "openai_pdf_model": "gpt-4o-mini",
            "openai_transcription_model": "gpt-4o-mini-transcribe",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["jurisdiction"] == "US-CA"
    assert body["base_currency"] == "MXN"
    assert body["fiscal_year_start_month"] == 4
    assert body["ai_provider"] == "openai"
    assert body["ai_model"] == "gpt-4.1-mini"
    assert body["openai_document_ai_enabled"] is True
    assert body["openai_document_ai_consent_granted"] is True
    assert body["openai_vision_model"] == "gpt-4o-mini"
    assert body["openai_pdf_model"] == "gpt-4o-mini"
    assert body["openai_transcription_model"] == "gpt-4o-mini-transcribe"

    row = (
        await db.execute(
            select(UserSettings).where(UserSettings.user_id == uuid.UUID(seeded["user_id"]))
        )
    ).scalar_one()
    assert row.base_currency == "MXN"
    assert row.fiscal_year_start_month == 4


async def test_settings_put_encrypts_api_key_and_stores_hint(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    api_key = "sk-test-secret-1234"

    response = await client.put(
        "/settings",
        json={"ai_provider": "openai", "ai_api_key": api_key},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_api_key_present"] is True
    assert body["ai_api_key_hint"] == "1234"

    row = (
        await db.execute(
            select(UserSettings).where(UserSettings.user_id == uuid.UUID(seeded["user_id"]))
        )
    ).scalar_one()
    assert row.ai_api_key_encrypted is not None
    assert api_key.encode("utf-8") not in row.ai_api_key_encrypted
    assert row.ai_api_key_hint == "1234"
    assert decrypt_secret(row.ai_api_key_encrypted) == api_key


async def test_settings_get_never_exposes_encrypted_blob(client: AsyncClient, seeded: dict) -> None:
    await _login_seeded_owner(client, seeded)
    await client.put("/settings", json={"ai_api_key": "sk-test-secret-5678"})

    response = await client.get("/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["ai_api_key_present"] is True
    assert body["ai_api_key_hint"] == "5678"
    assert "ai_api_key_encrypted" not in body


async def test_settings_put_clear_wipes_key(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    await client.put("/settings", json={"ai_api_key": "sk-test-secret-9999"})

    response = await client.put("/settings", json={"ai_api_key_clear": True})

    assert response.status_code == 200
    body = response.json()
    assert body["ai_api_key_present"] is False
    assert body["ai_api_key_hint"] is None

    row = (
        await db.execute(
            select(UserSettings).where(UserSettings.user_id == uuid.UUID(seeded["user_id"]))
        )
    ).scalar_one()
    assert row.ai_api_key_encrypted is None
    assert row.ai_api_key_hint is None


async def test_settings_update_writes_redacted_audit(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    api_key = "sk-live-super-secret-2468"

    response = await client.put(
        "/settings",
        json={"jurisdiction": "US-CA", "ai_provider": "openai", "ai_api_key": api_key},
    )

    assert response.status_code == 200
    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.action == "update",
                AuditLog.object_type == "user_settings",
            )
        )
    ).scalar_one_or_none()
    assert audit is not None
    assert api_key not in str(audit.before)
    assert api_key not in str(audit.after)
    assert audit.after["ai_api_key"] == "[REDACTED]"


async def test_crypto_round_trip() -> None:
    secret = "provider-secret-value"
    ciphertext = encrypt_secret(secret)

    assert ciphertext != secret.encode("utf-8")
    assert decrypt_secret(ciphertext) == secret
