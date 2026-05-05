from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import (
    DB,
    CurrentUserDep,
    RequestCtx,
    require_poster,
    require_reader,
    require_writer,
)
from app.models import Entity, EntityMember
from app.schemas.journal import (
    JournalEntryCreate,
    JournalEntryOut,
    JournalEntryUpdate,
    VoidRequest,
)
from app.services.audit import write_audit
from app.services.journal import (
    create_draft,
    delete_draft,
    get_entry_scoped,
    list_entries,
    post_entry,
    serialize_entry,
    update_draft,
    void_entry,
)

router = APIRouter(prefix="/entities/{entity_id}/journal-entries", tags=["journal"])


@router.get("", response_model=list[JournalEntryOut])
async def list_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[JournalEntryOut]:
    rows = await list_entries(db, entity_id=entity_id, limit=limit, offset=offset)
    return [JournalEntryOut.model_validate(r) for r in rows]


@router.post("", response_model=JournalEntryOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    entity_id: uuid.UUID,
    payload: JournalEntryCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> JournalEntryOut:
    entry = await create_draft(db, entity_id=entity_id, user_id=me.id, payload=payload)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="create",
        object_type="journal_entry",
        object_id=entry.id,
        after=serialize_entry(entry),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return JournalEntryOut.model_validate(entry)


@router.get("/{entry_id}", response_model=JournalEntryOut)
async def get_endpoint(
    entity_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
) -> JournalEntryOut:
    entry = await get_entry_scoped(db, entity_id=entity_id, entry_id=entry_id)
    return JournalEntryOut.model_validate(entry)


@router.patch("/{entry_id}", response_model=JournalEntryOut)
async def update_endpoint(
    entity_id: uuid.UUID,
    entry_id: uuid.UUID,
    payload: JournalEntryUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> JournalEntryOut:
    entry = await get_entry_scoped(db, entity_id=entity_id, entry_id=entry_id)
    before = serialize_entry(entry)
    entry = await update_draft(db, entry, payload=payload)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="update",
        object_type="journal_entry",
        object_id=entry.id,
        before=before,
        after=serialize_entry(entry),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return JournalEntryOut.model_validate(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_endpoint(
    entity_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> Response:
    entry = await get_entry_scoped(db, entity_id=entity_id, entry_id=entry_id)
    before = serialize_entry(entry)
    await delete_draft(db, entry)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="delete",
        object_type="journal_entry",
        object_id=entry_id,
        before=before,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{entry_id}/post", response_model=JournalEntryOut)
async def post_endpoint(
    entity_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_poster)],
) -> JournalEntryOut:
    entry = await get_entry_scoped(db, entity_id=entity_id, entry_id=entry_id)
    before = serialize_entry(entry)
    entry = await post_entry(db, entry, posted_by_id=me.id)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="post",
        object_type="journal_entry",
        object_id=entry.id,
        before=before,
        after=serialize_entry(entry),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return JournalEntryOut.model_validate(entry)


@router.post("/{entry_id}/void", response_model=JournalEntryOut)
async def void_endpoint(
    entity_id: uuid.UUID,
    entry_id: uuid.UUID,
    payload: VoidRequest,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_poster)],
) -> JournalEntryOut:
    entry = await get_entry_scoped(db, entity_id=entity_id, entry_id=entry_id)
    before = serialize_entry(entry)
    entry, reversal = await void_entry(
        db, entry, voided_by_id=me.id, reason=payload.reason
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="void",
        object_type="journal_entry",
        object_id=entry.id,
        before=before,
        after={
            "voided": serialize_entry(entry),
            "reversal": serialize_entry(reversal),
        },
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return JournalEntryOut.model_validate(entry)
