from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, NotFoundError, FinClawError
from app.models import Account, AccountType, NormalSide
from app.models.account import NORMAL_SIDE_FOR_TYPE


async def list_accounts(db: AsyncSession, *, entity_id: uuid.UUID) -> list[Account]:
    rows = (
        await db.execute(
            select(Account).where(Account.entity_id == entity_id).order_by(Account.code)
        )
    ).scalars()
    return list(rows)


async def get_account_scoped(
    db: AsyncSession, *, entity_id: uuid.UUID, account_id: uuid.UUID
) -> Account:
    acct = await db.get(Account, account_id)
    if acct is None or acct.entity_id != entity_id:
        raise NotFoundError(f"Account {account_id} not found", code="account_not_found")
    return acct


def _check_normal_side(type_: AccountType, normal_side: NormalSide) -> None:
    expected = NORMAL_SIDE_FOR_TYPE[type_]
    if normal_side != expected:
        raise FinClawError(
            f"Account type {type_.value} requires normal_side={expected.value}",
            code="invalid_normal_side",
        )


async def create_account(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    code: str,
    name: str,
    type: AccountType,
    normal_side: NormalSide | None = None,
    parent_id: uuid.UUID | None = None,
    description: str | None = None,
) -> Account:
    if normal_side is None:
        normal_side = NORMAL_SIDE_FOR_TYPE[type]
    _check_normal_side(type, normal_side)

    if parent_id is not None:
        parent = await get_account_scoped(db, entity_id=entity_id, account_id=parent_id)
        if parent.type != type:
            raise FinClawError(
                f"Parent account type ({parent.type.value}) must match child type ({type.value})",
                code="parent_type_mismatch",
            )

    acct = Account(
        entity_id=entity_id,
        code=code,
        name=name,
        type=type,
        normal_side=normal_side,
        parent_id=parent_id,
        description=description,
    )
    db.add(acct)
    try:
        await db.flush()
    except IntegrityError as e:
        raise ConflictError(
            f"Account code '{code}' already exists for this entity",
            code="duplicate_account_code",
        ) from e
    return acct


async def update_account(
    db: AsyncSession,
    account: Account,
    *,
    code: str | None = None,
    name: str | None = None,
    parent_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    description: str | None = None,
) -> Account:
    if code is not None:
        account.code = code
    if name is not None:
        account.name = name
    if parent_id is not None:
        if parent_id == account.id:
            raise FinClawError(
                "Account cannot be its own parent",
                code="self_parent",
            )
        parent = await get_account_scoped(
            db, entity_id=account.entity_id, account_id=parent_id
        )
        if parent.type != account.type:
            raise FinClawError(
                "Parent account type must match",
                code="parent_type_mismatch",
            )
        account.parent_id = parent_id
    if is_active is not None:
        account.is_active = is_active
    if description is not None:
        account.description = description

    try:
        await db.flush()
    except IntegrityError as e:
        raise ConflictError(
            f"Account code '{account.code}' already exists for this entity",
            code="duplicate_account_code",
        ) from e
    return account


async def delete_account(db: AsyncSession, account: Account) -> None:
    """Soft validation: refuse if any journal lines reference this account.

    For Phase 1 we rely on the journal_lines.account_id FK with ondelete=RESTRICT
    to surface the violation; we translate it into a friendly error.
    """
    try:
        await db.delete(account)
        await db.flush()
    except IntegrityError as e:
        raise ConflictError(
            "Account cannot be deleted; it is referenced by journal lines",
            code="account_in_use",
        ) from e
