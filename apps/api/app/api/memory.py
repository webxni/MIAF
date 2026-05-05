from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep, DB, RequestCtx
from app.models import MemoryType
from app.schemas.memory import MemoryCreate, MemoryOut, MemoryReviewCreate, MemoryReviewOut, MemoryUpdate
from app.services.audit import write_audit
from app.services.memory import (
    delete_memory,
    expire_memory,
    get_memory_scoped,
    list_memories,
    create_memory,
    review_memory,
    update_memory,
)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=list[MemoryOut])
async def search_memory(
    db: DB,
    me: CurrentUserDep,
    query: str | None = None,
    memory_type: MemoryType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[MemoryOut]:
    rows = await list_memories(
        db,
        tenant_id=me.tenant_id,
        query=query,
        memory_type=memory_type,
        limit=limit,
    )
    return [MemoryOut.model_validate(row) for row in rows]


@router.post("", response_model=MemoryOut)
async def add_memory(
    payload: MemoryCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> MemoryOut:
    row = await create_memory(db, tenant_id=me.tenant_id, user_id=me.id, payload=payload)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=payload.entity_id,
        action="create",
        object_type="memory",
        object_id=row.id,
        after={"memory_type": row.memory_type.value, "title": row.title},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return MemoryOut.model_validate(row)


@router.get("/{memory_id}", response_model=MemoryOut)
async def get_memory(
    memory_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
) -> MemoryOut:
    row = await get_memory_scoped(db, tenant_id=me.tenant_id, memory_id=memory_id, accessed_by_id=me.id)
    return MemoryOut.model_validate(row)


@router.patch("/{memory_id}", response_model=MemoryOut)
async def patch_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> MemoryOut:
    row = await get_memory_scoped(db, tenant_id=me.tenant_id, memory_id=memory_id)
    before = {"title": row.title, "is_active": row.is_active}
    row = await update_memory(db, row, payload=payload, user_id=me.id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=row.entity_id,
        action="update",
        object_type="memory",
        object_id=row.id,
        before=before,
        after={"title": row.title, "is_active": row.is_active},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return MemoryOut.model_validate(row)


@router.post("/{memory_id}/review", response_model=MemoryReviewOut)
async def post_memory_review(
    memory_id: uuid.UUID,
    payload: MemoryReviewCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> MemoryReviewOut:
    memory = await get_memory_scoped(db, tenant_id=me.tenant_id, memory_id=memory_id)
    review = await review_memory(db, memory, payload=payload, reviewer_user_id=me.id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=memory.entity_id,
        action="review",
        object_type="memory",
        object_id=memory.id,
        after={"status": payload.status.value, "notes": payload.notes},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return MemoryReviewOut.model_validate(review)


@router.post("/{memory_id}/expire", response_model=MemoryOut)
async def post_memory_expire(
    memory_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> MemoryOut:
    memory = await get_memory_scoped(db, tenant_id=me.tenant_id, memory_id=memory_id)
    memory = await expire_memory(db, memory, user_id=me.id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=memory.entity_id,
        action="expire",
        object_type="memory",
        object_id=memory.id,
        after={"is_active": memory.is_active, "expires_at": memory.expires_at.isoformat() if memory.expires_at else None},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return MemoryOut.model_validate(memory)


@router.delete("/{memory_id}", status_code=204)
async def forget_memory(
    memory_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
) -> None:
    memory = await get_memory_scoped(db, tenant_id=me.tenant_id, memory_id=memory_id)
    await delete_memory(db, memory, user_id=me.id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=memory.entity_id,
        action="delete",
        object_type="memory",
        object_id=memory.id,
        after={"is_active": memory.is_active},
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
