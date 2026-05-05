from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import (
    DB,
    CurrentUserDep,
    RequestCtx,
    require_reader,
    require_writer,
)
from app.models import Entity, EntityMember
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.services.accounts import (
    create_account,
    delete_account,
    get_account_scoped,
    list_accounts,
    update_account,
)
from app.services.audit import write_audit

router = APIRouter(prefix="/entities/{entity_id}/accounts", tags=["accounts"])


def _account_dict(a) -> dict:
    return {
        "id": str(a.id),
        "code": a.code,
        "name": a.name,
        "type": a.type.value,
        "normal_side": a.normal_side.value,
        "parent_id": str(a.parent_id) if a.parent_id else None,
        "is_active": a.is_active,
    }


@router.get("", response_model=list[AccountOut])
async def list_accounts_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
) -> list[AccountOut]:
    rows = await list_accounts(db, entity_id=entity_id)
    return [AccountOut.model_validate(r) for r in rows]


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_account_endpoint(
    entity_id: uuid.UUID,
    payload: AccountCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> AccountOut:
    acct = await create_account(
        db,
        entity_id=entity_id,
        code=payload.code,
        name=payload.name,
        type=payload.type,
        normal_side=payload.normal_side,
        parent_id=payload.parent_id,
        description=payload.description,
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="create",
        object_type="account",
        object_id=acct.id,
        after=_account_dict(acct),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return AccountOut.model_validate(acct)


@router.get("/{account_id}", response_model=AccountOut)
async def get_account_endpoint(
    entity_id: uuid.UUID,
    account_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
) -> AccountOut:
    acct = await get_account_scoped(db, entity_id=entity_id, account_id=account_id)
    return AccountOut.model_validate(acct)


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account_endpoint(
    entity_id: uuid.UUID,
    account_id: uuid.UUID,
    payload: AccountUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> AccountOut:
    acct = await get_account_scoped(db, entity_id=entity_id, account_id=account_id)
    before = _account_dict(acct)
    acct = await update_account(
        db,
        acct,
        code=payload.code,
        name=payload.name,
        parent_id=payload.parent_id,
        is_active=payload.is_active,
        description=payload.description,
    )
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="update",
        object_type="account",
        object_id=acct.id,
        before=before,
        after=_account_dict(acct),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return AccountOut.model_validate(acct)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_account_endpoint(
    entity_id: uuid.UUID,
    account_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> Response:
    acct = await get_account_scoped(db, entity_id=entity_id, account_id=account_id)
    before = _account_dict(acct)
    await delete_account(db, acct)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="delete",
        object_type="account",
        object_id=account_id,
        before=before,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
