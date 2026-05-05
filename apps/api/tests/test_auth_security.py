from __future__ import annotations

import uuid

import pytest
from fastapi import Response
from sqlalchemy import select

from app.api.auth import login
from app.api.deps import RequestContext
from app.errors import AuthError
from app.models import AuditLog, LoginAttempt
from app.schemas.auth import LoginRequest

pytestmark = pytest.mark.asyncio


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
    assert "finclaw_session=" in response.headers.get("set-cookie", "")


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
