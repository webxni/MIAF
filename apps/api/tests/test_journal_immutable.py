"""Posted entries are immutable. Voiding goes through reversal entries."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.errors import ImmutableEntryError
from app.models import Account, JournalEntryStatus
from app.schemas.journal import JournalEntryCreate, JournalEntryUpdate, JournalLineIn
from app.services.journal import (
    create_draft,
    delete_draft,
    post_entry,
    update_draft,
    void_entry,
)


pytestmark = pytest.mark.asyncio


async def _accounts(db, entity_id):
    rows = (
        await db.execute(select(Account).where(Account.entity_id == entity_id))
    ).scalars().all()
    return {a.code: a for a in rows}


async def _post_simple(db, entity_id, user_id, accounts, amount: Decimal = Decimal("12.34")):
    payload = JournalEntryCreate(
        entry_date=date(2026, 5, 4),
        memo="Test",
        lines=[
            JournalLineIn(account_id=accounts["5200"].id, debit=amount, credit=Decimal("0")),
            JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("0"), credit=amount),
        ],
    )
    entry = await create_draft(db, entity_id=entity_id, user_id=user_id, payload=payload)
    return await post_entry(db, entry, posted_by_id=user_id)


async def test_posted_entry_cannot_be_updated(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)
    posted = await _post_simple(db, entity_id, user_id, accounts)

    with pytest.raises(ImmutableEntryError) as exc:
        await update_draft(
            db,
            posted,
            payload=JournalEntryUpdate(memo="hacked"),
        )
    assert exc.value.code == "entry_not_draft"


async def test_posted_entry_cannot_be_deleted(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)
    posted = await _post_simple(db, entity_id, user_id, accounts)

    with pytest.raises(ImmutableEntryError) as exc:
        await delete_draft(db, posted)
    assert exc.value.code == "entry_not_draft"


async def test_posted_entry_cannot_be_reposted(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)
    posted = await _post_simple(db, entity_id, user_id, accounts)

    with pytest.raises(ImmutableEntryError):
        await post_entry(db, posted, posted_by_id=user_id)


async def test_void_creates_reversal_and_marks_original(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)
    posted = await _post_simple(db, entity_id, user_id, accounts, amount=Decimal("50.00"))

    voided, reversal = await void_entry(db, posted, voided_by_id=user_id, reason="duplicate")

    assert voided.status == JournalEntryStatus.voided
    assert voided.voided_reason == "duplicate"
    assert voided.voided_by_entry_id == reversal.id

    assert reversal.status == JournalEntryStatus.posted
    assert reversal.voids_entry_id == voided.id
    assert len(reversal.lines) == len(voided.lines)
    # Each reversal line is the original with debit/credit swapped.
    by_acct_orig = {ln.account_id: (ln.debit, ln.credit) for ln in voided.lines}
    by_acct_rev = {ln.account_id: (ln.debit, ln.credit) for ln in reversal.lines}
    for acct, (d, c) in by_acct_orig.items():
        rd, rc = by_acct_rev[acct]
        assert rd == c
        assert rc == d


async def test_voided_entry_cannot_be_voided_again(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)
    posted = await _post_simple(db, entity_id, user_id, accounts)
    voided, _ = await void_entry(db, posted, voided_by_id=user_id, reason="x")

    with pytest.raises(ImmutableEntryError):
        await void_entry(db, voided, voided_by_id=user_id, reason="again")


async def test_draft_can_be_updated_and_deleted(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)

    draft = await create_draft(
        db,
        entity_id=entity_id,
        user_id=user_id,
        payload=JournalEntryCreate(
            entry_date=date(2026, 5, 4),
            lines=[
                JournalLineIn(account_id=accounts["5200"].id, debit=Decimal("1.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("0"), credit=Decimal("1.00")),
            ],
        ),
    )
    updated = await update_draft(db, draft, payload=JournalEntryUpdate(memo="ok"))
    assert updated.memo == "ok"

    await delete_draft(db, updated)
