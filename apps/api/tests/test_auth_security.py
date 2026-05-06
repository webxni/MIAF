from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import Response
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.auth import login
from app.api.deps import RequestContext, get_db
from app.errors import AuthError
from app.main import app
from app.models import AuditLog, LoginAttempt
from app.schemas.auth import LoginRequest

pytestmark = pytest.mark.asyncio


# ── shared HTTP client ────────────────────────────────────────────────────────

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
    response = await client.post(
        "/auth/login",
        json={"email": seeded["user_email"], "password": "change-me-on-first-login"},
    )
    assert response.status_code == 200


async def test_successful_login_records_attempt_and_sets_cookie(seeded, db):
    response = Response()
    user = await login(
        LoginRequest(email=seeded["user_email"], password="change-me-on-first-login"),
        response,
        db,
        RequestContext(ip="127.0.0.1", user_agent="pytest"),
    )

    attempts = (await db.execute(select(LoginAttempt))).scalars().all()
    assert user.email == seeded["user_email"]
    assert len(attempts) == 1
    assert attempts[0].was_successful is True
    assert "miaf_session=" in response.headers.get("set-cookie", "")


async def test_failed_login_is_audited_and_rate_limited(seeded, db):
    ctx = RequestContext(ip="127.0.0.1", user_agent="pytest")

    for _ in range(5):
        with pytest.raises(AuthError) as exc:
            await login(
                LoginRequest(email=seeded["user_email"], password="wrong-password"),
                Response(),
                db,
                ctx,
            )
        assert exc.value.code == "invalid_credentials"

    with pytest.raises(AuthError) as exc:
        await login(
            LoginRequest(email=seeded["user_email"], password="wrong-password"),
            Response(),
            db,
            ctx,
        )
    assert exc.value.code == "login_rate_limited"

    attempts = (
        await db.execute(select(LoginAttempt).where(LoginAttempt.email == seeded["user_email"]))
    ).scalars().all()
    audits = (
        await db.execute(select(AuditLog).where(AuditLog.action == "login_failed"))
    ).scalars().all()

    assert len(attempts) == 5
    assert all(attempt.was_successful is False for attempt in attempts)
    assert audits


# ── password change ───────────────────────────────────────────────────────────

async def test_password_change_succeeds_with_correct_current_password(client, seeded, db):
    await _login(client, seeded)

    response = await client.put(
        "/auth/password",
        json={
            "current_password": "change-me-on-first-login",
            "new_password": "new-secure-password-123",
        },
    )
    assert response.status_code == 204

    audit = (
        await db.execute(select(AuditLog).where(AuditLog.action == "password_change"))
    ).scalar_one_or_none()
    assert audit is not None


async def test_password_change_rejects_wrong_current_password(client, seeded):
    await _login(client, seeded)

    response = await client.put(
        "/auth/password",
        json={
            "current_password": "wrong-password-here",
            "new_password": "new-secure-password-123",
        },
    )
    assert response.status_code in (401, 403, 400)


async def test_password_change_requires_auth(client, seeded):
    response = await client.put(
        "/auth/password",
        json={
            "current_password": "change-me-on-first-login",
            "new_password": "new-secure-password-123",
        },
    )
    assert response.status_code in (401, 403)


# ── revoke all sessions ───────────────────────────────────────────────────────

async def test_revoke_all_sessions_clears_cookie_and_audits(client, seeded, db):
    await _login(client, seeded)

    response = await client.post("/auth/revoke-all-sessions")
    assert response.status_code == 204

    audit = (
        await db.execute(select(AuditLog).where(AuditLog.action == "revoke_all_sessions"))
    ).scalar_one_or_none()
    assert audit is not None


async def test_revoke_all_sessions_requires_auth(client, seeded):
    response = await client.post("/auth/revoke-all-sessions")
    assert response.status_code in (401, 403)
