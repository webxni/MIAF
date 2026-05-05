from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models import Entity, EntityMember, EntityMode, Role


async def list_entities_for_user(db: AsyncSession, *, user_id: uuid.UUID) -> list[Entity]:
    rows = (
        await db.execute(
            select(Entity)
            .join(EntityMember, EntityMember.entity_id == Entity.id)
            .where(EntityMember.user_id == user_id)
            .order_by(Entity.created_at)
        )
    ).scalars()
    return list(rows)


async def get_entity_scoped(
    db: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> Entity:
    entity = await db.get(Entity, entity_id)
    if entity is None or entity.tenant_id != tenant_id:
        raise NotFoundError(f"Entity {entity_id} not found", code="entity_not_found")
    return entity


async def create_entity(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    owner_user_id: uuid.UUID,
    name: str,
    mode: EntityMode,
    currency: str = "USD",
) -> Entity:
    entity = Entity(tenant_id=tenant_id, name=name, mode=mode, currency=currency.upper())
    db.add(entity)
    await db.flush()
    db.add(EntityMember(entity_id=entity.id, user_id=owner_user_id, role=Role.owner))
    await db.flush()
    return entity


async def update_entity(
    db: AsyncSession,
    entity: Entity,
    *,
    name: str | None = None,
    currency: str | None = None,
) -> Entity:
    if name is not None:
        entity.name = name
    if currency is not None:
        entity.currency = currency.upper()
    await db.flush()
    return entity
