from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.main import app
from app.models import AuditLog, Entity, EntityMember, EntityMode, Role, Tenant, User
from app.models.base import utcnow
from app.security import hash_password
from app.services.audit import write_audit

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


async def _login(client: AsyncClient, *, email: str, password: str) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200


async def _login_seeded_owner(client: AsyncClient, seeded: dict) -> None:
    await _login(
        client,
        email=seeded["user_email"],
        password="change-me-on-first-login",
    )


async def _create_viewer_user(db, seeded: dict) -> User:
    user = User(
        tenant_id=uuid.UUID(seeded["tenant_id"]),
        email="viewer@example.com",
        name="Viewer User",
        password_hash=hash_password("viewer-password"),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    entity_ids = [
        uuid.UUID(seeded["personal_entity_id"]),
        uuid.UUID(seeded["business_entity_id"]),
    ]
    for entity_id in entity_ids:
        db.add(EntityMember(entity_id=entity_id, user_id=user.id, role=Role.viewer))
    await db.flush()
    return user


async def _create_other_tenant_row(db) -> AuditLog:
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

    row = AuditLog(
        tenant_id=tenant.id,
        user_id=user.id,
        entity_id=entity.id,
        action="isolation_check",
        object_type="memory",
        object_id=str(entity.id),
        after={"tenant": "other"},
        created_at=utcnow(),
    )
    db.add(row)
    await db.flush()
    return row


async def test_owner_can_list_audit_logs_after_actions(client: AsyncClient, seeded: dict) -> None:
    await _login_seeded_owner(client, seeded)
    entity_id = seeded["personal_entity_id"]

    for idx in range(3):
        response = await client.post(
            "/memory",
            json={
                "memory_type": "advisor_note",
                "title": f"Audit note {idx}",
                "content": f"Row {idx}",
                "summary": f"Summary {idx}",
                "keywords": ["audit", str(idx)],
                "source": "user",
                "entity_id": entity_id,
                "consent_granted": True,
            },
        )
        assert response.status_code == 200

    response = await client.get("/audit-logs?limit=50&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 4
    assert len(body["rows"]) >= 4
    create_rows = [row for row in body["rows"] if row["action"] == "create" and row["object_type"] == "memory"]
    assert len(create_rows) == 3
    assert all(row["entity_id"] == entity_id for row in create_rows)
    assert all("id" in row for row in create_rows)
    assert body["rows"][0]["created_at"] >= body["rows"][-1]["created_at"]


async def test_viewer_only_user_gets_403(client: AsyncClient, seeded: dict, db) -> None:
    viewer = await _create_viewer_user(db, seeded)
    await _login(client, email=viewer.email, password="viewer-password")

    response = await client.get("/audit-logs")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "role_forbidden"


async def test_filter_by_action_works(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])

    await write_audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=entity_id,
        action="filter_target",
        object_type="memory",
        object_id=entity_id,
        after={"kind": "wanted"},
    )
    await write_audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=entity_id,
        action="filter_other",
        object_type="memory",
        object_id=entity_id,
        after={"kind": "other"},
    )

    response = await client.get("/audit-logs?action=filter_target")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["rows"]) == 1
    assert body["rows"][0]["action"] == "filter_target"


async def test_filter_by_since_works(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    base = utcnow()

    older = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=entity_id,
        action="since_check",
        object_type="memory",
        object_id="older",
        after={"order": "older"},
        created_at=base,
    )
    newer = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=entity_id,
        action="since_check",
        object_type="memory",
        object_id="newer",
        after={"order": "newer"},
        created_at=base + timedelta(minutes=5),
    )
    db.add_all([older, newer])
    await db.flush()

    response = await client.get(f"/audit-logs?action=since_check&since={newer.created_at.isoformat().replace('+', '%2B')}")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [row["object_id"] for row in body["rows"]] == ["newer"]


async def test_cross_tenant_isolation_hides_other_tenant_rows(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])

    await write_audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=entity_id,
        action="isolation_check",
        object_type="memory",
        object_id=entity_id,
        after={"tenant": "seeded"},
    )
    other_row = await _create_other_tenant_row(db)

    response = await client.get("/audit-logs?action=isolation_check")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["rows"]) == 1
    assert body["rows"][0]["id"] != str(other_row.id)
    assert body["rows"][0]["after"] == {"tenant": "seeded"}


async def test_pagination_limit_and_offset_cover_all_rows(client: AsyncClient, seeded: dict, db) -> None:
    await _login_seeded_owner(client, seeded)
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    base = utcnow()

    for idx in range(4):
        db.add(
            AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                entity_id=entity_id,
                action="page_check",
                object_type="memory",
                object_id=f"page-{idx}",
                after={"idx": idx},
                created_at=base + timedelta(minutes=idx),
            )
        )
    await db.flush()

    first = await client.get("/audit-logs?action=page_check&limit=2&offset=0")
    second = await client.get("/audit-logs?action=page_check&limit=2&offset=2")

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["total"] == 4
    assert second_body["total"] == 4
    assert len(first_body["rows"]) == 2
    assert len(second_body["rows"]) == 2

    seen = [row["object_id"] for row in first_body["rows"] + second_body["rows"]]
    assert seen == ["page-3", "page-2", "page-1", "page-0"]
    assert len(set(seen)) == 4
