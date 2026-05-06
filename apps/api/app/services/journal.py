"""Journal entry service: draft / update / post / void.

Invariants enforced here:
- Posted entries are immutable (status, lines, dates).
- Posting requires balanced lines (sum debits == sum credits, > 0).
- Every line is single-sided (DB CHECK enforces that too).
- All referenced accounts must belong to the entry's entity.
- Voiding is via reversal: a new entry with debit/credit swapped is created and
  the original is marked voided with cross-references.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import (
    MIAFError,
    ImmutableEntryError,
    NotFoundError,
    UnbalancedEntryError,
)
from app.models import Account, AccountType, Entity, JournalEntry, JournalEntryStatus, JournalLine, SourceTransaction
from app.models.base import utcnow
from app.money import ZERO, to_money
from app.schemas.journal import JournalLineIn
from app.services.classifier import classify_source_transaction, record_merchant_correction


# --------- helpers ----------------------------------------------------------


def _validate_balance(lines: list[JournalLineIn] | list[JournalLine]) -> tuple[Decimal, Decimal]:
    """Returns (total_debit, total_credit). Raises if sums don't match or are zero.

    Each line must be single-sided. Quantizes to 2 dp before comparing.
    """
    total_debit = ZERO
    total_credit = ZERO
    for ln in lines:
        d = to_money(ln.debit or ZERO)
        c = to_money(ln.credit or ZERO)
        if (d > ZERO and c > ZERO) or (d == ZERO and c == ZERO):
            raise UnbalancedEntryError(
                "Each line must have exactly one of debit or credit > 0",
                code="line_not_single_sided",
            )
        if d < ZERO or c < ZERO:
            raise UnbalancedEntryError(
                "Debit and credit must be non-negative",
                code="negative_amount",
            )
        total_debit += d
        total_credit += c
    if total_debit == ZERO:
        raise UnbalancedEntryError(
            "Journal entry has zero total amount",
            code="zero_total",
        )
    if total_debit != total_credit:
        raise UnbalancedEntryError(
            "Total debits must equal total credits",
            code="unbalanced",
            details={
                "total_debit": str(total_debit),
                "total_credit": str(total_credit),
                "difference": str(total_debit - total_credit),
            },
        )
    return total_debit, total_credit


async def _validate_accounts_belong_to_entity(
    db: AsyncSession, entity_id: uuid.UUID, account_ids: list[uuid.UUID]
) -> None:
    if not account_ids:
        return
    rows = (
        await db.execute(
            select(Account.id, Account.entity_id, Account.is_active).where(
                Account.id.in_(account_ids)
            )
        )
    ).all()
    seen = {r.id for r in rows}
    missing = set(account_ids) - seen
    if missing:
        raise NotFoundError(
            f"Account(s) not found: {sorted(str(m) for m in missing)}",
            code="account_not_found",
        )
    wrong_entity = [str(r.id) for r in rows if r.entity_id != entity_id]
    if wrong_entity:
        raise MIAFError(
            f"Account(s) do not belong to entity: {wrong_entity}",
            code="account_wrong_entity",
        )
    inactive = [str(r.id) for r in rows if not r.is_active]
    if inactive:
        raise MIAFError(
            f"Account(s) are inactive: {inactive}",
            code="account_inactive",
        )


async def _validate_linked_entry(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    linked_entry_id: uuid.UUID | None,
) -> None:
    if linked_entry_id is None:
        return

    current_entity = await db.get(Entity, entity_id)
    if current_entity is None:
        raise NotFoundError(f"Entity {entity_id} not found", code="entity_not_found")

    linked = (
        await db.execute(
            select(JournalEntry.id, JournalEntry.entity_id, Entity.tenant_id)
            .join(Entity, Entity.id == JournalEntry.entity_id)
            .where(JournalEntry.id == linked_entry_id)
        )
    ).first()
    if linked is None:
        raise NotFoundError(
            f"Linked journal entry {linked_entry_id} not found",
            code="linked_entry_not_found",
        )
    if linked.tenant_id != current_entity.tenant_id:
        raise MIAFError(
            "Linked journal entry belongs to a different tenant",
            code="linked_entry_wrong_tenant",
        )


def serialize_entry(entry: JournalEntry) -> dict:
    """Plain dict for audit logs."""
    return {
        "id": str(entry.id),
        "entry_date": entry.entry_date.isoformat(),
        "memo": entry.memo,
        "reference": entry.reference,
        "status": entry.status.value,
        "lines": [
            {
                "id": str(ln.id),
                "account_id": str(ln.account_id),
                "line_no": ln.line_no,
                "debit": str(ln.debit),
                "credit": str(ln.credit),
                "description": ln.description,
            }
            for ln in entry.lines
        ],
    }


# --------- public API -------------------------------------------------------


async def get_entry_scoped(
    db: AsyncSession, *, entity_id: uuid.UUID, entry_id: uuid.UUID
) -> JournalEntry:
    entry = (
        await db.execute(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.id == entry_id)
        )
    ).scalar_one_or_none()
    if entry is None or entry.entity_id != entity_id:
        raise NotFoundError(f"Journal entry {entry_id} not found", code="entry_not_found")
    return entry


async def list_entries(
    db: AsyncSession, *, entity_id: uuid.UUID, limit: int = 100, offset: int = 0
) -> list[JournalEntry]:
    rows = (
        await db.execute(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.entity_id == entity_id)
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars()
    return list(rows)


async def create_draft(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    user_id: uuid.UUID | None,
    payload,  # JournalEntryCreate
) -> JournalEntry:
    await _validate_accounts_belong_to_entity(
        db, entity_id, [ln.account_id for ln in payload.lines]
    )
    await _validate_linked_entry(
        db,
        entity_id=entity_id,
        linked_entry_id=payload.linked_entry_id,
    )
    # We don't require balance for drafts but lines must be valid (single-sided, non-negative).
    # Run the per-line check by converting each via _validate_balance — but allow unbalanced totals
    # by catching the unbalanced error specifically? Simpler: enforce single-sidedness inline.
    for ln in payload.lines:
        d = to_money(ln.debit or ZERO)
        c = to_money(ln.credit or ZERO)
        if (d > ZERO and c > ZERO) or (d == ZERO and c == ZERO):
            raise UnbalancedEntryError(
                "Each line must have exactly one of debit or credit > 0",
                code="line_not_single_sided",
            )
        if d < ZERO or c < ZERO:
            raise UnbalancedEntryError("Debit and credit must be non-negative", code="negative_amount")

    entry = JournalEntry(
        entity_id=entity_id,
        entry_date=payload.entry_date,
        memo=payload.memo,
        reference=payload.reference,
        status=JournalEntryStatus.draft,
        linked_entry_id=payload.linked_entry_id,
        source_transaction_id=payload.source_transaction_id,
        created_by_id=user_id,
    )
    db.add(entry)
    await db.flush()

    for i, ln in enumerate(payload.lines, start=1):
        db.add(
            JournalLine(
                journal_entry_id=entry.id,
                account_id=ln.account_id,
                line_no=i,
                debit=to_money(ln.debit or ZERO),
                credit=to_money(ln.credit or ZERO),
                description=ln.description,
            )
        )
    await db.flush()
    await db.refresh(entry, attribute_names=["lines"])
    return entry


async def update_draft(
    db: AsyncSession,
    entry: JournalEntry,
    *,
    payload,  # JournalEntryUpdate
) -> JournalEntry:
    if entry.status != JournalEntryStatus.draft:
        raise ImmutableEntryError(
            f"Cannot edit entry in status {entry.status.value}; only drafts are mutable",
            code="entry_not_draft",
        )

    if payload.entry_date is not None:
        entry.entry_date = payload.entry_date
    if payload.memo is not None:
        entry.memo = payload.memo
    if payload.reference is not None:
        entry.reference = payload.reference
    if payload.linked_entry_id is not None:
        await _validate_linked_entry(
            db,
            entity_id=entry.entity_id,
            linked_entry_id=payload.linked_entry_id,
        )
        entry.linked_entry_id = payload.linked_entry_id

    if payload.lines is not None:
        await _validate_accounts_belong_to_entity(
            db, entry.entity_id, [ln.account_id for ln in payload.lines]
        )
        # Replace lines wholesale (drafts only).
        for old in list(entry.lines):
            await db.delete(old)
        await db.flush()
        for i, ln in enumerate(payload.lines, start=1):
            d = to_money(ln.debit or ZERO)
            c = to_money(ln.credit or ZERO)
            if (d > ZERO and c > ZERO) or (d == ZERO and c == ZERO):
                raise UnbalancedEntryError(
                    "Each line must have exactly one of debit or credit > 0",
                    code="line_not_single_sided",
                )
            db.add(
                JournalLine(
                    journal_entry_id=entry.id,
                    account_id=ln.account_id,
                    line_no=i,
                    debit=d,
                    credit=c,
                    description=ln.description,
                )
            )
    await db.flush()
    await db.refresh(entry, attribute_names=["lines"])
    return entry


async def delete_draft(db: AsyncSession, entry: JournalEntry) -> None:
    if entry.status != JournalEntryStatus.draft:
        raise ImmutableEntryError(
            f"Cannot delete entry in status {entry.status.value}",
            code="entry_not_draft",
        )
    await db.delete(entry)
    await db.flush()


async def _learn_merchant_rule_from_posted_entry(
    db: AsyncSession,
    entry: JournalEntry,
    *,
    posted_by_id: uuid.UUID,
) -> None:
    if entry.source_transaction_id is None:
        return

    source_tx = await db.get(SourceTransaction, entry.source_transaction_id)
    if source_tx is None or not (source_tx.merchant or "").strip():
        return

    entity = await db.get(Entity, entry.entity_id)
    if entity is None:
        return

    accounts = (
        await db.execute(select(Account).where(Account.entity_id == entry.entity_id).order_by(Account.code))
    ).scalars().all()
    accounts_by_id = {account.id: account for account in accounts}
    actual_expense_account = next(
        (
            accounts_by_id[line.account_id]
            for line in entry.lines
            if line.debit > ZERO
            and accounts_by_id.get(line.account_id) is not None
            and accounts_by_id[line.account_id].type == AccountType.expense
        ),
        None,
    )
    if actual_expense_account is None:
        return

    active_accounts = [account for account in accounts if account.is_active]
    suggested_account, _ = classify_source_transaction(
        source_tx,
        active_accounts,
        memory_lookup=None,
    )
    if suggested_account.code == actual_expense_account.code:
        return

    await record_merchant_correction(
        db,
        tenant_id=entity.tenant_id,
        user_id=posted_by_id,
        entity_id=entry.entity_id,
        merchant=source_tx.merchant or "",
        account=actual_expense_account,
    )


async def post_entry(
    db: AsyncSession, entry: JournalEntry, *, posted_by_id: uuid.UUID
) -> JournalEntry:
    if entry.status != JournalEntryStatus.draft:
        raise ImmutableEntryError(
            f"Only drafts can be posted (current: {entry.status.value})",
            code="entry_not_draft",
        )
    if not entry.lines:
        raise UnbalancedEntryError(
            "Cannot post an entry with no lines", code="no_lines"
        )
    _validate_balance(entry.lines)

    entry.status = JournalEntryStatus.posted
    entry.posted_at = utcnow()
    entry.posted_by_id = posted_by_id
    await db.flush()
    try:
        await _learn_merchant_rule_from_posted_entry(
            db,
            entry,
            posted_by_id=posted_by_id,
        )
    except Exception:
        pass
    return entry


async def void_entry(
    db: AsyncSession,
    entry: JournalEntry,
    *,
    voided_by_id: uuid.UUID,
    reason: str | None,
) -> tuple[JournalEntry, JournalEntry]:
    """Void a posted entry by creating a reversal entry.

    Returns (original_voided, reversal_entry). The reversal is created as
    `posted` directly — it represents the irrevocable correction of an
    already-recorded fact.
    """
    if entry.status == JournalEntryStatus.draft:
        raise ImmutableEntryError(
            "Drafts are not voided; delete them instead", code="entry_is_draft"
        )
    if entry.status == JournalEntryStatus.voided:
        raise ImmutableEntryError(
            "Entry is already voided", code="entry_already_voided"
        )

    now = utcnow()
    reversal = JournalEntry(
        entity_id=entry.entity_id,
        entry_date=entry.entry_date,
        memo=f"Reversal of {entry.id}" + (f": {reason}" if reason else ""),
        reference=entry.reference,
        status=JournalEntryStatus.posted,
        posted_at=now,
        posted_by_id=voided_by_id,
        voids_entry_id=entry.id,
        created_by_id=voided_by_id,
    )
    db.add(reversal)
    await db.flush()

    for i, ln in enumerate(entry.lines, start=1):
        db.add(
            JournalLine(
                journal_entry_id=reversal.id,
                account_id=ln.account_id,
                line_no=i,
                # Swap sides
                debit=ln.credit,
                credit=ln.debit,
                description=f"Reverse: {ln.description or ''}".strip(": "),
            )
        )

    entry.status = JournalEntryStatus.voided
    entry.voided_at = now
    entry.voided_by_id = voided_by_id
    entry.voided_reason = reason
    entry.voided_by_entry_id = reversal.id

    await db.flush()
    await db.refresh(reversal, attribute_names=["lines"])
    await db.refresh(entry, attribute_names=["lines"])
    return entry, reversal
