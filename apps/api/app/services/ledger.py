"""General ledger query: lines for one account in a date range, with running balance."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models import (
    Account,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
    NormalSide,
)
from app.money import ZERO, to_money
from app.schemas.ledger import LedgerLine, LedgerResponse


def _signed(debit: Decimal, credit: Decimal, normal_side: NormalSide) -> Decimal:
    """Effect on the account's balance, expressed in its normal-side direction."""
    if normal_side == NormalSide.debit:
        return debit - credit
    return credit - debit


async def general_ledger(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    account_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> LedgerResponse:
    account = await db.get(Account, account_id)
    if account is None or account.entity_id != entity_id:
        raise NotFoundError("Account not found", code="account_not_found")

    base_filters = [
        JournalLine.account_id == account_id,
        JournalEntry.entity_id == entity_id,
        # Drafts excluded; voided entries are kept (their reversal cancels them).
        JournalEntry.status.in_([JournalEntryStatus.posted, JournalEntryStatus.voided]),
    ]

    # Opening balance: posted lines before date_from.
    opening = ZERO
    if date_from is not None:
        sums = (
            await db.execute(
                select(
                    func.coalesce(func.sum(JournalLine.debit), 0).label("d"),
                    func.coalesce(func.sum(JournalLine.credit), 0).label("c"),
                )
                .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
                .where(*base_filters, JournalEntry.entry_date < date_from)
            )
        ).first()
        if sums:
            opening = _signed(Decimal(sums.d), Decimal(sums.c), account.normal_side)

    # Lines in range.
    range_filters = list(base_filters)
    if date_from is not None:
        range_filters.append(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        range_filters.append(JournalEntry.entry_date <= date_to)

    rows = (
        await db.execute(
            select(
                JournalEntry.id.label("entry_id"),
                JournalEntry.entry_date,
                JournalEntry.memo,
                JournalEntry.reference,
                JournalLine.id.label("line_id"),
                JournalLine.debit,
                JournalLine.credit,
                JournalLine.description,
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(*range_filters)
            .order_by(JournalEntry.entry_date, JournalEntry.created_at, JournalLine.line_no)
        )
    ).all()

    running = opening
    total_d = ZERO
    total_c = ZERO
    lines: list[LedgerLine] = []
    for r in rows:
        d = to_money(r.debit)
        c = to_money(r.credit)
        running += _signed(d, c, account.normal_side)
        total_d += d
        total_c += c
        lines.append(
            LedgerLine(
                entry_id=r.entry_id,
                line_id=r.line_id,
                entry_date=r.entry_date,
                memo=r.memo,
                reference=r.reference,
                debit=d,
                credit=c,
                description=r.description,
                running_balance=to_money(running),
            )
        )

    return LedgerResponse(
        account_id=account.id,
        account_code=account.code,
        account_name=account.name,
        account_type=account.type,
        normal_side=account.normal_side,
        opening_balance=to_money(opening),
        total_debit=to_money(total_d),
        total_credit=to_money(total_c),
        closing_balance=to_money(running),
        lines=lines,
    )
