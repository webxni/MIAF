"""Verify the seed creates the contractual artifacts: tenant, user, personal + business entities, default COAs."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.models import (
    Account,
    AccountType,
    Entity,
    EntityMember,
    EntityMode,
    Role,
    Tenant,
    User,
)


pytestmark = pytest.mark.asyncio


async def test_seed_creates_one_tenant_and_user(seeded, db):
    tenant_count = (await db.execute(select(func.count(Tenant.id)))).scalar_one()
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    assert tenant_count == 1
    assert user_count == 1


async def test_seed_creates_personal_and_business_entity(seeded, db):
    rows = (await db.execute(select(Entity).order_by(Entity.created_at))).scalars().all()
    modes = sorted(e.mode for e in rows)
    assert modes == [EntityMode.business, EntityMode.personal] or modes == [EntityMode.personal, EntityMode.business]
    assert len(rows) == 2


async def test_seed_grants_owner_membership(seeded, db):
    members = (await db.execute(select(EntityMember))).scalars().all()
    assert len(members) == 2
    assert all(m.role == Role.owner for m in members)


async def test_seed_creates_default_charts_of_accounts(seeded, db):
    personal_id = uuid.UUID(seeded["personal_entity_id"])
    business_id = uuid.UUID(seeded["business_entity_id"])

    p_count = (
        await db.execute(select(func.count(Account.id)).where(Account.entity_id == personal_id))
    ).scalar_one()
    b_count = (
        await db.execute(select(func.count(Account.id)).where(Account.entity_id == business_id))
    ).scalar_one()

    assert p_count > 10  # personal COA has ~26 accounts
    assert b_count > 10  # business COA has ~28 accounts

    # Each entity must have at least one of every account type.
    for entity_id in (personal_id, business_id):
        types = (
            await db.execute(
                select(Account.type).where(Account.entity_id == entity_id).distinct()
            )
        ).scalars().all()
        assert set(types) == set(AccountType)


async def test_seed_is_idempotent(db):
    from app.services.seed import run_seed

    first = await run_seed(db)
    await db.flush()
    second = await run_seed(db)
    await db.flush()
    assert first["tenant_id"] == second["tenant_id"]
    assert first["user_id"] == second["user_id"]
    assert first["personal_entity_id"] == second["personal_entity_id"]
    assert second["personal_accounts_created"] == 0
    assert second["business_accounts_created"] == 0
