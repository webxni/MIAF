"""Tests for the multi-user team invite flow."""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.errors import AuthError, ConflictError
from app.main import app
from app.models import AuditLog, EntityMember, InviteToken, User
from app.models.base import utcnow
from app.services.invite import (
    accept_invite,
    create_invite,
    list_invites,
    revoke_invite,
)
from app.models.entity import Role

pytestmark = pytest.mark.asyncio


# ── Service-layer unit tests ──────────────────────────────────────────────────

async def test_create_invite_produces_token(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    inviter_id = uuid.UUID(seeded["user_id"])

    invite = await create_invite(db, tenant_id=tenant_id, inviter_id=inviter_id, email="new@example.com", role=Role.viewer)

    assert invite.token
    assert invite.email == "new@example.com"
    assert invite.role == Role.viewer.value
    assert invite.is_revoked is False
    assert invite.accepted_at is None


async def test_create_invite_deduplicates_pending(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    inviter_id = uuid.UUID(seeded["user_id"])

    inv1 = await create_invite(db, tenant_id=tenant_id, inviter_id=inviter_id, email="dup@example.com", role=Role.viewer)
    inv2 = await create_invite(db, tenant_id=tenant_id, inviter_id=inviter_id, email="dup@example.com", role=Role.accountant)
    assert inv1.id == inv2.id
    assert inv2.role == Role.accountant.value


async def test_create_invite_rejects_existing_member(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    inviter_id = uuid.UUID(seeded["user_id"])

    with pytest.raises(ConflictError) as exc:
        await create_invite(db, tenant_id=tenant_id, inviter_id=inviter_id, email=seeded["user_email"], role=Role.viewer)
    assert exc.value.code == "invite_already_member"


async def test_accept_invite_creates_user_and_memberships(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    inviter_id = uuid.UUID(seeded["user_id"])

    invite = await create_invite(db, tenant_id=tenant_id, inviter_id=inviter_id, email="invited@example.com", role=Role.accountant)
    user = await accept_invite(db, token=invite.token, name="Invited Person", password="secure-pass-123")

    assert user.email == "invited@example.com"
    assert user.tenant_id == tenant_id

    memberships = (
        await db.execute(select(EntityMember).where(EntityMember.user_id == user.id))
    ).scalars().all()
    assert len(memberships) > 0
    assert all(m.role == Role.accountant for m in memberships)

    # Invite should now be marked accepted
    await db.refresh(invite)
    assert invite.accepted_at is not None


async def test_accept_invalid_token_raises(seeded, db):
    with pytest.raises(AuthError) as exc:
        await accept_invite(db, token="not-a-real-token", name="X", password="password123")
    assert exc.value.code == "invalid_invite"


async def test_accept_revoked_invite_raises(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    inviter_id = uuid.UUID(seeded["user_id"])

    invite = await create_invite(db, tenant_id=tenant_id, inviter_id=inviter_id, email="rev@example.com", role=Role.viewer)
    await revoke_invite(db, invite_id=invite.id, tenant_id=tenant_id)

    with pytest.raises(AuthError) as exc:
        await accept_invite(db, token=invite.token, name="X", password="pass1234")
    assert exc.value.code == "invite_revoked"


async def test_accept_expired_invite_raises(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    inviter_id = uuid.UUID(seeded["user_id"])

    invite = await create_invite(db, tenant_id=tenant_id, inviter_id=inviter_id, email="exp@example.com", role=Role.viewer)
    # Force expiry
    invite.expires_at = utcnow() - timedelta(hours=1)
    await db.flush()

    with pytest.raises(AuthError) as exc:
        await accept_invite(db, token=invite.token, name="X", password="pass1234")
    assert exc.value.code == "invite_expired"


async def test_revoke_invite(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    inviter_id = uuid.UUID(seeded["user_id"])

    invite = await create_invite(db, tenant_id=tenant_id, inviter_id=inviter_id, email="rvk@example.com", role=Role.viewer)
    revoked = await revoke_invite(db, invite_id=invite.id, tenant_id=tenant_id)
    assert revoked.is_revoked is True


async def test_list_invites_returns_tenant_scoped(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    inviter_id = uuid.UUID(seeded["user_id"])

    await create_invite(db, tenant_id=tenant_id, inviter_id=inviter_id, email="a@example.com", role=Role.viewer)
    await create_invite(db, tenant_id=tenant_id, inviter_id=inviter_id, email="b@example.com", role=Role.viewer)

    invites = await list_invites(db, tenant_id=tenant_id)
    assert len(invites) >= 2


# ── HTTP-level tests ──────────────────────────────────────────────────────────

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


async def test_create_invite_via_http_requires_auth(client, seeded):
    r = await client.post("/auth/invites", json={"email": "x@example.com", "role": "viewer"})
    assert r.status_code in (401, 403)


async def test_create_and_accept_invite_via_http(client, seeded, db):
    await _login(client, seeded)

    r = await client.post("/auth/invites", json={"email": "newmember@example.com", "role": "viewer"})
    assert r.status_code == 201
    data = r.json()
    token = data["id"]  # We'll fetch the real token from DB since the API doesn't expose it
    assert data["email"] == "newmember@example.com"

    audit = (
        await db.execute(select(AuditLog).where(AuditLog.action == "create_invite"))
    ).scalar_one_or_none()
    assert audit is not None

    # Fetch actual token from DB
    invite = (await db.execute(select(InviteToken).where(InviteToken.email == "newmember@example.com"))).scalar_one()

    # Accept through HTTP
    r2 = await client.post("/auth/accept-invite", json={
        "token": invite.token,
        "name": "New Member",
        "password": "secure-password-123",
    })
    assert r2.status_code == 200
    assert r2.json()["email"] == "newmember@example.com"

    accept_audit = (
        await db.execute(select(AuditLog).where(AuditLog.action == "accept_invite"))
    ).scalar_one_or_none()
    assert accept_audit is not None


async def test_list_invites_via_http(client, seeded):
    await _login(client, seeded)
    r = await client.get("/auth/invites")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_revoke_invite_via_http(client, seeded, db):
    await _login(client, seeded)

    r = await client.post("/auth/invites", json={"email": "todelete@example.com", "role": "viewer"})
    assert r.status_code == 201
    invite_id = r.json()["id"]

    r2 = await client.delete(f"/auth/invites/{invite_id}")
    assert r2.status_code == 204

    invite = await db.get(InviteToken, uuid.UUID(invite_id))
    assert invite.is_revoked is True
