"""Trial balance must reflect only posted, non-voided entries within the as-of date."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Account
from app.schemas.journal import JournalEntryCreate, JournalLineIn
from app.services.journal import create_draft, post_entry, void_entry
from app.services.trial_balance import trial_balance


pytestmark = pytest.mark.asyncio


async def _accounts(db, entity_id):
    rows = (
        await db.execute(select(Account).where(Account.entity_id == entity_id))
    ).scalars().all()
    return {a.code: a for a in rows}


async def test_empty_ledger_is_balanced(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    tb = await trial_balance(db, entity_id=entity_id, as_of=date(2026, 5, 5))
    assert tb.total_debit == Decimal("0.00")
    assert tb.total_credit == Decimal("0.00")
    assert tb.is_balanced is True
    assert tb.rows == []


async def test_posted_entry_appears_in_trial_balance(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    a = await _accounts(db, entity_id)

    payload = JournalEntryCreate(
        entry_date=date(2026, 5, 5),
        lines=[
            JournalLineIn(account_id=a["5200"].id, debit=Decimal("4.50"), credit=Decimal("0")),
            JournalLineIn(account_id=a["1110"].id, debit=Decimal("0"), credit=Decimal("4.50")),
        ],
    )
    entry = await create_draft(db, entity_id=entity_id, user_id=user_id, payload=payload)
    await post_entry(db, entry, posted_by_id=user_id)

    tb = await trial_balance(db, entity_id=entity_id, as_of=date(2026, 5, 5))
    assert tb.is_balanced
    assert tb.total_debit == Decimal("4.50")
    assert tb.total_credit == Decimal("4.50")
    assert len(tb.rows) == 2


async def test_draft_entries_do_not_affect_trial_balance(seeded, db):
    """Regression: trial balance must NOT count draft journal entries."""
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    a = await _accounts(db, entity_id)

    # Draft only — never posted.
    await create_draft(
        db,
        entity_id=entity_id,
        user_id=user_id,
        payload=JournalEntryCreate(
            entry_date=date(2026, 5, 5),
            lines=[
                JournalLineIn(account_id=a["5200"].id, debit=Decimal("100.00"), credit=Decimal("0")),
                JournalLineIn(account_id=a["1110"].id, debit=Decimal("0"), credit=Decimal("100.00")),
            ],
        ),
    )

    tb = await trial_balance(db, entity_id=entity_id, as_of=date(2026, 5, 5))
    assert tb.total_debit == Decimal("0.00")
    assert tb.total_credit == Decimal("0.00")
    assert tb.is_balanced
    assert tb.rows == []


async def test_voided_entry_zeroed_by_reversal(seeded, db):
    """A void produces a posted reversal — net effect on the trial balance is zero."""
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    a = await _accounts(db, entity_id)

    payload = JournalEntryCreate(
        entry_date=date(2026, 5, 5),
        lines=[
            JournalLineIn(account_id=a["5200"].id, debit=Decimal("12.00"), credit=Decimal("0")),
            JournalLineIn(account_id=a["1110"].id, debit=Decimal("0"), credit=Decimal("12.00")),
        ],
    )
    entry = await create_draft(db, entity_id=entity_id, user_id=user_id, payload=payload)
    await post_entry(db, entry, posted_by_id=user_id)

    tb_before = await trial_balance(db, entity_id=entity_id, as_of=date(2026, 5, 5))
    assert tb_before.total_debit == Decimal("12.00")

    await void_entry(db, entry, voided_by_id=user_id, reason="oops")

    tb_after = await trial_balance(db, entity_id=entity_id, as_of=date(2026, 5, 5))
    # Original is now voided (excluded). Reversal is posted with swapped sides.
    # Net per account = 0; trial balance shows no rows.
    assert tb_after.is_balanced
    assert tb_after.total_debit == Decimal("0.00")
    assert tb_after.rows == []


async def test_as_of_date_excludes_future_entries(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    a = await _accounts(db, entity_id)

    payload = JournalEntryCreate(
        entry_date=date(2026, 6, 15),  # future
        lines=[
            JournalLineIn(account_id=a["5200"].id, debit=Decimal("99.00"), credit=Decimal("0")),
            JournalLineIn(account_id=a["1110"].id, debit=Decimal("0"), credit=Decimal("99.00")),
        ],
    )
    entry = await create_draft(db, entity_id=entity_id, user_id=user_id, payload=payload)
    await post_entry(db, entry, posted_by_id=user_id)

    tb = await trial_balance(db, entity_id=entity_id, as_of=date(2026, 5, 31))
    assert tb.rows == []
    assert tb.total_debit == Decimal("0.00")
