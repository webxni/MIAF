"""Idempotent seed: tenant, default user, personal entity, business entity, default COAs."""
from __future__ import annotations

import logging
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Account,
    Entity,
    EntityMember,
    EntityMode,
    Role,
    Tenant,
    User,
)
from app.models.account import NORMAL_SIDE_FOR_TYPE
from app.security import hash_password
from app.services.coa import coa_for_mode

log = logging.getLogger("seed")


SEED_TENANT_NAME = "FinClaw Demo Tenant"
DEFAULT_SEED_USER_NAME = "Demo Owner"
DEFAULT_SEED_USER_PASSWORD = "change-me-on-first-login"
SEED_PERSONAL_NAME = "Personal"
SEED_BUSINESS_NAME = "My Business"


def _get_seed_config() -> tuple[str | None, str, str]:
    return (
        os.getenv("SEED_USER_EMAIL"),
        os.getenv("SEED_USER_NAME", DEFAULT_SEED_USER_NAME),
        os.getenv("SEED_USER_PASSWORD", DEFAULT_SEED_USER_PASSWORD),
    )


async def _get_or_create_tenant(db: AsyncSession) -> Tenant:
    existing = (
        await db.execute(select(Tenant).where(Tenant.name == SEED_TENANT_NAME))
    ).scalar_one_or_none()
    if existing:
        return existing
    t = Tenant(name=SEED_TENANT_NAME)
    db.add(t)
    await db.flush()
    log.info("seed: created tenant %s", t.id)
    return t


async def _get_or_create_user(
    db: AsyncSession,
    tenant: Tenant,
    *,
    email: str,
    name: str,
    password: str,
) -> User:
    existing = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing:
        return existing
    u = User(
        tenant_id=tenant.id,
        email=email,
        name=name,
        password_hash=hash_password(password),
    )
    db.add(u)
    await db.flush()
    log.info("seed: created user %s (%s)", u.email, u.id)
    return u


async def _get_or_create_entity(
    db: AsyncSession, tenant: Tenant, user: User, name: str, mode: EntityMode
) -> Entity:
    existing = (
        await db.execute(
            select(Entity).where(
                Entity.tenant_id == tenant.id,
                Entity.name == name,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    e = Entity(tenant_id=tenant.id, name=name, mode=mode, currency="USD")
    db.add(e)
    await db.flush()
    db.add(EntityMember(entity_id=e.id, user_id=user.id, role=Role.owner))
    await db.flush()
    log.info("seed: created entity %s (%s, %s)", name, mode.value, e.id)
    return e


async def create_default_chart_of_accounts(db: AsyncSession, entity: Entity) -> int:
    nodes = coa_for_mode(entity.mode)

    # Index existing accounts by code for idempotency.
    existing_rows = (
        await db.execute(select(Account).where(Account.entity_id == entity.id))
    ).scalars()
    existing_by_code: dict[str, Account] = {a.code: a for a in existing_rows}

    created = 0
    code_to_id: dict[str, str] = {c: a.id for c, a in existing_by_code.items()}

    # Two passes ensure parents exist before children even if order shifts.
    for pass_no in range(2):
        for node in nodes:
            if node.code in code_to_id:
                continue
            parent_id = None
            if node.parent_code is not None:
                parent_id = code_to_id.get(node.parent_code)
                if parent_id is None and pass_no == 0:
                    # Parent will be created later in this pass; skip for now.
                    continue
            acct = Account(
                entity_id=entity.id,
                code=node.code,
                name=node.name,
                type=node.type,
                normal_side=NORMAL_SIDE_FOR_TYPE[node.type],
                parent_id=parent_id,
                description=node.description,
            )
            db.add(acct)
            await db.flush()
            code_to_id[node.code] = acct.id
            created += 1
    if created:
        log.info("seed: created %d accounts on entity %s (%s)", created, entity.name, entity.id)
    return created


async def run_seed(db: AsyncSession) -> dict:
    seed_email, seed_name, seed_password = _get_seed_config()
    if not seed_email:
        log.info("seed: skipping demo workspace creation because SEED_USER_EMAIL is not set")
        return {"skipped": True}

    tenant = await _get_or_create_tenant(db)
    user = await _get_or_create_user(
        db,
        tenant,
        email=seed_email,
        name=seed_name,
        password=seed_password,
    )
    personal = await _get_or_create_entity(
        db, tenant, user, SEED_PERSONAL_NAME, EntityMode.personal
    )
    business = await _get_or_create_entity(
        db, tenant, user, SEED_BUSINESS_NAME, EntityMode.business
    )
    personal_created = await create_default_chart_of_accounts(db, personal)
    business_created = await create_default_chart_of_accounts(db, business)
    return {
        "tenant_id": str(tenant.id),
        "user_id": str(user.id),
        "user_email": user.email,
        "personal_entity_id": str(personal.id),
        "business_entity_id": str(business.id),
        "personal_accounts_created": personal_created,
        "business_accounts_created": business_created,
    }
