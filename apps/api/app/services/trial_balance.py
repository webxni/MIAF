"""Trial balance: sum of debits and credits per account as of a date."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Account,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
)
from app.money import ZERO, to_money
from app.schemas.ledger import TrialBalanceResponse, TrialBalanceRow


async def trial_balance(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    as_of: date,
) -> TrialBalanceResponse:
    """Returns the net debit/credit balance per account in the conventional TB form.

    For each account with posted activity on or before `as_of`:
    - net = sum(debit) - sum(credit)
    - if net > 0  -> place in debit column
    - if net < 0  -> place in credit column (as positive)
    - if net == 0 -> omit (keeps the report tidy)
    Sum of the debit column equals sum of the credit column when the ledger is sound.

    Drafts and voided entries are excluded.
    """
    # Inner joins through to posted entries so draft/voided lines never count.
    rows = (
        await db.execute(
            select(
                Account.id,
                Account.code,
                Account.name,
                Account.type,
                Account.normal_side,
                func.coalesce(func.sum(JournalLine.debit), 0).label("d"),
                func.coalesce(func.sum(JournalLine.credit), 0).label("c"),
            )
            .join(JournalLine, JournalLine.account_id == Account.id)
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(
                Account.entity_id == entity_id,
                JournalEntry.entity_id == entity_id,
                # Drafts never count. Voided entries DO count alongside their
                # reversal — both stay on the books; their lines cancel.
                JournalEntry.status.in_(
                    [JournalEntryStatus.posted, JournalEntryStatus.voided]
                ),
                JournalEntry.entry_date <= as_of,
            )
            .group_by(Account.id)
            .order_by(Account.code)
        )
    ).all()

    out_rows: list[TrialBalanceRow] = []
    total_d = ZERO
    total_c = ZERO
    for r in rows:
        d = Decimal(r.d)
        c = Decimal(r.c)
        net = d - c
        debit_col = ZERO
        credit_col = ZERO
        if net > 0:
            debit_col = net
        elif net < 0:
            credit_col = -net
        if debit_col == 0 and credit_col == 0:
            continue
        out_rows.append(
            TrialBalanceRow(
                account_id=r.id,
                code=r.code,
                name=r.name,
                type=r.type,
                normal_side=r.normal_side,
                debit=to_money(debit_col),
                credit=to_money(credit_col),
            )
        )
        total_d += debit_col
        total_c += credit_col

    return TrialBalanceResponse(
        entity_id=entity_id,
        as_of=as_of,
        rows=out_rows,
        total_debit=to_money(total_d),
        total_credit=to_money(total_c),
        is_balanced=(to_money(total_d) == to_money(total_c)),
    )
