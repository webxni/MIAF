from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.main import app
from app.models import Alert, AlertSeverity, AlertStatus, AuditLog, Entity, EntityMember, EntityMode, HeartbeatRun, HeartbeatRunStatus, HeartbeatType, Role, Tenant, User
from app.models.base import utcnow
from app.security import hash_password

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


async def _create_alert(
    db,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    status: AlertStatus = AlertStatus.open,
) -> Alert:
    run = HeartbeatRun(
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.daily_personal_check,
        status=HeartbeatRunStatus.completed,
        trigger_source="manual",
        started_at=utcnow(),
        finished_at=utcnow(),
    )
    db.add(run)
    await db.flush()

    alert = Alert(
        tenant_id=tenant_id,
        entity_id=entity_id,
        heartbeat_run_id=run.id,
        alert_type="test_alert",
        severity=AlertSeverity.warning,
        status=status,
        title="Test alert",
        message="Test alert message",
        resolved_at=utcnow() if status == AlertStatus.resolved else None,
    )
    db.add(alert)
    await db.flush()
    return alert


async def _create_other_tenant_alert(db) -> Alert:
    tenant = Tenant(name="Other Tenant")
    db.add(tenant)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email="other-owner@example.com",
        name="Other Owner",
        password_hash=hash_password("other-password"),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    entity = Entity(tenant_id=tenant.id, name="Other Entity", mode=EntityMode.business, currency="USD")
    db.add(entity)
    await db.flush()

    db.add(EntityMember(entity_id=entity.id, user_id=user.id, role=Role.owner))
    await db.flush()

    return await _create_alert(db, tenant_id=tenant.id, entity_id=entity.id)


async def test_dismiss_alert_flips_status_and_writes_audit(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    alert = await _create_alert(
        db,
        tenant_id=uuid.UUID(seeded["tenant_id"]),
        entity_id=uuid.UUID(seeded["personal_entity_id"]),
    )

    response = await client.post(f"/heartbeat/alerts/{alert.id}/dismiss", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dismissed"
    assert body["resolved_at"] is None

    refreshed = await db.get(Alert, alert.id)
    assert refreshed is not None
    assert refreshed.status == AlertStatus.dismissed
    assert refreshed.resolved_at is None

    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.object_type == "alert",
                AuditLog.object_id == str(alert.id),
                AuditLog.action == "update",
            )
        )
    ).scalar_one()
    assert audit.before == {"status": "open", "resolved_at": None}
    assert audit.after == {"status": "dismissed", "resolved_at": None}


async def test_resolve_alert_flips_status_sets_resolved_at_and_writes_audit(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    alert = await _create_alert(
        db,
        tenant_id=uuid.UUID(seeded["tenant_id"]),
        entity_id=uuid.UUID(seeded["business_entity_id"]),
    )

    response = await client.post(f"/heartbeat/alerts/{alert.id}/resolve", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None

    refreshed = await db.get(Alert, alert.id)
    assert refreshed is not None
    assert refreshed.status == AlertStatus.resolved
    assert refreshed.resolved_at is not None

    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.object_type == "alert",
                AuditLog.object_id == str(alert.id),
                AuditLog.action == "update",
            )
        )
    ).scalar_one()
    assert audit.before == {"status": "open", "resolved_at": None}
    assert audit.after is not None
    assert audit.after["status"] == "resolved"
    assert audit.after["resolved_at"] is not None


async def test_dismiss_and_resolve_on_resolved_alert_return_invalid_transition(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    alert = await _create_alert(
        db,
        tenant_id=uuid.UUID(seeded["tenant_id"]),
        entity_id=uuid.UUID(seeded["personal_entity_id"]),
        status=AlertStatus.resolved,
    )

    dismiss_response = await client.post(f"/heartbeat/alerts/{alert.id}/dismiss", json={})
    resolve_response = await client.post(f"/heartbeat/alerts/{alert.id}/resolve", json={})

    for response in (dismiss_response, resolve_response):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_alert_transition"


async def test_cross_tenant_alert_action_returns_not_found(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    alert = await _create_other_tenant_alert(db)

    response = await client.post(f"/heartbeat/alerts/{alert.id}/dismiss", json={})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "alert_not_found"
