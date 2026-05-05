from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    DB,
    CurrentUserDep,
    RequestCtx,
    get_entity_for_user,
    require_role,
)
from app.models import Entity, EntityMember, Role
from app.schemas.entity import EntityCreate, EntityOut, EntityUpdate
from app.services.audit import write_audit
from app.services.entities import (
    create_entity,
    list_entities_for_user,
    update_entity,
)

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=list[EntityOut])
async def list_entities(db: DB, me: CurrentUserDep) -> list[EntityOut]:
    rows = await list_entities_for_user(db, user_id=me.id)
    return [EntityOut.model_validate(r) for r in rows]


@router.post("", response_model=EntityOut, status_code=status.HTTP_201_CREATED)
async def create_entity_endpoint(
    payload: EntityCreate, db: DB, me: CurrentUserDep, ctx: RequestCtx
) -> EntityOut:
    entity = await create_entity(
        db,
        tenant_id=me.tenant_id,
        owner_user_id=me.id,
        name=payload.name,
        mode=payload.mode,
        currency=payload.currency,
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity.id,
        action="create",
        object_type="entity",
        object_id=entity.id,
        after={
            "id": str(entity.id),
            "name": entity.name,
            "mode": entity.mode.value,
            "currency": entity.currency,
        },
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return EntityOut.model_validate(entity)


@router.get("/{entity_id}", response_model=EntityOut)
async def get_entity_endpoint(
    entity_id: uuid.UUID,
    scoped: Annotated[
        tuple[Entity, EntityMember], Depends(get_entity_for_user)
    ],
) -> EntityOut:
    entity, _ = scoped
    return EntityOut.model_validate(entity)


@router.patch("/{entity_id}", response_model=EntityOut)
async def update_entity_endpoint(
    entity_id: uuid.UUID,
    payload: EntityUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[
        tuple[Entity, EntityMember],
        Depends(require_role(Role.owner, Role.admin)),
    ],
) -> EntityOut:
    entity, _ = scoped
    before = {"name": entity.name, "currency": entity.currency}
    entity = await update_entity(db, entity, name=payload.name, currency=payload.currency)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity.id,
        action="update",
        object_type="entity",
        object_id=entity.id,
        before=before,
        after={"name": entity.name, "currency": entity.currency},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return EntityOut.model_validate(entity)
