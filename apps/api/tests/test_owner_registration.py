from __future__ import annotations

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


async def test_register_owner_creates_tenant_user_entities(client, db):
    response = await client.post(
        "/auth/register-owner",
        json={
            "name": "First Owner",
            "email": "owner@finclaw.example.com",
            "password": "very-secure-password",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "owner@finclaw.example.com"
    assert "finclaw_session=" in response.headers.get("set-cookie", "")

    me_response = await client.get("/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "owner@finclaw.example.com"

    entities_response = await client.get("/entities")
    assert entities_response.status_code == 200
    entities = entities_response.json()
    assert len(entities) == 2
    assert {entity["mode"] for entity in entities} == {"personal", "business"}

    for entity in entities:
        accounts_response = await client.get(f"/entities/{entity['id']}/accounts")
        assert accounts_response.status_code == 200
        assert len(accounts_response.json()) > 10


async def test_register_owner_rejects_when_user_exists(client):
    first = await client.post(
        "/auth/register-owner",
        json={
            "name": "First Owner",
            "email": "owner@finclaw.example.com",
            "password": "very-secure-password",
        },
    )
    assert first.status_code == 200

    second = await client.post(
        "/auth/register-owner",
        json={
            "name": "Second Owner",
            "email": "second@finclaw.example.com",
            "password": "another-secure-password",
        },
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "owner_already_exists"


async def test_register_owner_rejects_short_password(client):
    response = await client.post(
        "/auth/register-owner",
        json={
            "name": "Short Password",
            "email": "owner@finclaw.example.com",
            "password": "short-pass",
        },
    )
    assert response.status_code == 422


async def test_register_owner_writes_audit_log(client, db):
    response = await client.post(
        "/auth/register-owner",
        json={
            "name": "First Owner",
            "email": "owner@finclaw.example.com",
            "password": "very-secure-password",
        },
    )
    assert response.status_code == 200

    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.action == "register_owner",
                AuditLog.object_type == "user",
            )
        )
    ).scalar_one_or_none()
    assert audit is not None
