"""Phase 1 acceptance tests: balanced JE posts, unbalanced rejected, posted JE immutable."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.errors import ImmutableEntryError, UnbalancedEntryError
from app.models import Account, JournalEntry, JournalEntryStatus
from app.schemas.journal import JournalEntryCreate, JournalEntryUpdate, JournalLineIn
from app.services.journal import (
    create_draft,
    delete_draft,
    post_entry,
    update_draft,
    void_entry,
)


pytestmark = pytest.mark.asyncio


async def _accounts(db, entity_id: uuid.UUID) -> dict[str, Account]:
    rows = (
        await db.execute(select(Account).where(Account.entity_id == entity_id))
    ).scalars().all()
    return {a.code: a for a in rows}


async def test_balanced_entry_can_post(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    a = await _accounts(db, entity_id)

    payload = JournalEntryCreate(
        entry_date=date(2026, 5, 4),
        memo="Coffee",
        lines=[
            JournalLineIn(account_id=a["5200"].id, debit=Decimal("4.50"), credit=Decimal("0")),
            JournalLineIn(account_id=a["1110"].id, debit=Decimal("0"), credit=Decimal("4.50")),
        ],
    )
    entry = await create_draft(db, entity_id=entity_id, user_id=user_id, payload=payload)
    assert entry.status == JournalEntryStatus.draft

    posted = await post_entry(db, entry, posted_by_id=user_id)
    assert posted.status == JournalEntryStatus.posted
    assert posted.posted_at is not None
    assert posted.posted_by_id == user_id


async def test_unbalanced_entry_cannot_post(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    a = await _accounts(db, entity_id)

    payload = JournalEntryCreate(
        entry_date=date(2026, 5, 4),
        memo="Bad",
        lines=[
            JournalLineIn(account_id=a["5200"].id, debit=Decimal("10.00"), credit=Decimal("0")),
            JournalLineIn(account_id=a["1110"].id, debit=Decimal("0"), credit=Decimal("9.99")),
        ],
    )
    entry = await create_draft(db, entity_id=entity_id, user_id=user_id, payload=payload)

    with pytest.raises(UnbalancedEntryError) as exc:
        await post_entry(db, entry, posted_by_id=user_id)
    assert exc.value.code == "unbalanced"
    # Entry stays a draft — posting failed atomically.
    assert entry.status == JournalEntryStatus.draft


async def test_zero_total_entry_cannot_post(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    a = await _accounts(db, entity_id)

    # Create a draft with valid lines, then mutate one to zero by replacing
    # via update_draft. Skipping the schema layer keeps the test focused on
    # the service's defense in depth.
    payload = JournalEntryCreate(
        entry_date=date(2026, 5, 4),
        lines=[
            JournalLineIn(account_id=a["5200"].id, debit=Decimal("1.00"), credit=Decimal("0")),
            JournalLineIn(account_id=a["1110"].id, debit=Decimal("0"), credit=Decimal("1.00")),
        ],
    )
    entry = await create_draft(db, entity_id=entity_id, user_id=user_id, payload=payload)

    # Both lines zero — should be rejected on update.
    with pytest.raises(UnbalancedEntryError):
        await update_draft(
            db,
            entry,
            payload=JournalEntryUpdate(
                lines=[
                    JournalLineIn(account_id=a["5200"].id, debit=Decimal("0"), credit=Decimal("0")),
                    JournalLineIn(account_id=a["1110"].id, debit=Decimal("0"), credit=Decimal("0")),
                ]
            ),
        )


async def test_double_sided_line_rejected(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    a = await _accounts(db, entity_id)

    payload = JournalEntryCreate(
        entry_date=date(2026, 5, 4),
        lines=[
            JournalLineIn(account_id=a["5200"].id, debit=Decimal("10.00"), credit=Decimal("10.00")),
            JournalLineIn(account_id=a["1110"].id, debit=Decimal("0"), credit=Decimal("10.00")),
        ],
    )
    with pytest.raises(UnbalancedEntryError) as exc:
        await create_draft(db, entity_id=entity_id, user_id=user_id, payload=payload)
    assert exc.value.code == "line_not_single_sided"


async def test_account_must_belong_to_entity(seeded, db):
    personal_id = uuid.UUID(seeded["personal_entity_id"])
    business_id = uuid.UUID(seeded["business_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    p = await _accounts(db, personal_id)
    b = await _accounts(db, business_id)

    payload = JournalEntryCreate(
        entry_date=date(2026, 5, 4),
        lines=[
            JournalLineIn(account_id=p["5200"].id, debit=Decimal("5.00"), credit=Decimal("0")),
            # business account on a personal entry — must be rejected
            JournalLineIn(account_id=b["1110"].id, debit=Decimal("0"), credit=Decimal("5.00")),
        ],
    )
    with pytest.raises(Exception) as exc:
        await create_draft(db, entity_id=personal_id, user_id=user_id, payload=payload)
    # service raises FinClawError with code account_wrong_entity
    assert "account_wrong_entity" in str(exc.value) or "account_wrong_entity" == getattr(exc.value, "code", "")
