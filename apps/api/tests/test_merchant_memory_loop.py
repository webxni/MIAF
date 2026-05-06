from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Account, AuditLog, JournalEntry, Memory, MemoryType
from app.schemas.journal import JournalEntryUpdate, JournalLineIn
from app.services.classifier import record_merchant_correction
from app.services.ingestion import import_csv_transactions
from app.services.journal import post_entry, update_draft


pytestmark = pytest.mark.asyncio


async def _account_by_code(db, entity_id: uuid.UUID, code: str) -> Account:
    account = (
        await db.execute(select(Account).where(Account.entity_id == entity_id, Account.code == code))
    ).scalar_one()
    return account


async def _draft_entries(db, entity_id: uuid.UUID) -> list[JournalEntry]:
    return (
        await db.execute(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.entity_id == entity_id)
            .order_by(JournalEntry.created_at, JournalEntry.id)
        )
    ).scalars().all()


async def _replace_debit_account(
    db,
    entry: JournalEntry,
    *,
    account_id: uuid.UUID,
) -> JournalEntry:
    updated_lines = []
    for line in entry.lines:
        next_account_id = account_id if line.debit > 0 else line.account_id
        updated_lines.append(
            JournalLineIn(
                account_id=next_account_id,
                debit=line.debit,
                credit=line.credit,
                description=line.description,
            )
        )
    return await update_draft(
        db,
        entry,
        payload=JournalEntryUpdate(lines=updated_lines),
    )


def _merchant_rule_rows(rows: list[Memory], merchant: str) -> list[Memory]:
    normalized = merchant.strip().lower()
    return [
        row
        for row in rows
        if row.memory_type == MemoryType.merchant_rule
        and isinstance(row.keywords, dict)
        and row.keywords.get("merchant") == normalized
    ]


async def test_correction_creates_merchant_rule(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    utilities = await _account_by_code(db, entity_id, "5400")

    await import_csv_transactions(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="bank.csv",
        content_type="text/csv",
        data=(
            "date,amount,merchant,memo,currency,external_ref\n"
            "2026-05-01,-12.34,ShellX,gas station fill-up,USD,tx-1\n"
        ).encode("utf-8"),
    )

    draft = (await _draft_entries(db, entity_id))[0]
    draft = await _replace_debit_account(db, draft, account_id=utilities.id)
    await post_entry(db, draft, posted_by_id=user_id)

    memories = (await db.execute(select(Memory).where(Memory.tenant_id == tenant_id))).scalars().all()
    rules = _merchant_rule_rows(memories, "ShellX")

    assert len(rules) == 1
    assert rules[0].keywords == {"merchant": "shellx", "account_code": "5400"}


async def test_no_rule_when_user_keeps_suggestion(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])

    await import_csv_transactions(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="bank.csv",
        content_type="text/csv",
        data=(
            "date,amount,merchant,memo,currency,external_ref\n"
            "2026-05-01,-12.34,ShellX,gas station fill-up,USD,tx-1\n"
        ).encode("utf-8"),
    )

    draft = (await _draft_entries(db, entity_id))[0]
    await post_entry(db, draft, posted_by_id=user_id)

    memories = (await db.execute(select(Memory).where(Memory.tenant_id == tenant_id))).scalars().all()
    assert _merchant_rule_rows(memories, "ShellX") == []


async def test_existing_rule_overrides_keyword_on_next_import(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    utilities = await _account_by_code(db, entity_id, "5400")

    await record_merchant_correction(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=entity_id,
        merchant="ShellX",
        account=utilities,
    )

    await import_csv_transactions(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="bank.csv",
        content_type="text/csv",
        data=(
            "date,amount,merchant,memo,currency,external_ref\n"
            "2026-05-02,-18.00,ShellX gas station,gas station fill-up,USD,tx-2\n"
        ).encode("utf-8"),
    )

    entry = (await _draft_entries(db, entity_id))[0]
    accounts = {
        account.id: account
        for account in (
            await db.execute(select(Account).where(Account.entity_id == entity_id))
        ).scalars().all()
    }
    debit_line = next(line for line in entry.lines if line.debit > 0)
    audit = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == entity_id, AuditLog.action == "auto_draft")
            .order_by(AuditLog.created_at.desc())
        )
    ).scalars().first()

    assert accounts[debit_line.account_id].code == "5400"
    assert audit is not None
    assert audit.after["classifier_reason"] == "memory:merchant_rule"


async def test_rule_idempotent_on_repeated_correction(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    utilities = await _account_by_code(db, entity_id, "5400")
    health = await _account_by_code(db, entity_id, "5500")

    await import_csv_transactions(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="bank-1.csv",
        content_type="text/csv",
        data=(
            "date,amount,merchant,memo,currency,external_ref\n"
            "2026-05-01,-12.34,ShellX,gas station fill-up,USD,tx-1\n"
        ).encode("utf-8"),
    )
    first_draft = (await _draft_entries(db, entity_id))[0]
    first_draft = await _replace_debit_account(db, first_draft, account_id=utilities.id)
    await post_entry(db, first_draft, posted_by_id=user_id)

    await import_csv_transactions(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        filename="bank-2.csv",
        content_type="text/csv",
        data=(
            "date,amount,merchant,memo,currency,external_ref\n"
            "2026-05-02,-15.00,ShellX,gas station fill-up,USD,tx-2\n"
        ).encode("utf-8"),
    )
    drafts = await _draft_entries(db, entity_id)
    second_draft = next(entry for entry in drafts if entry.status.value == "draft")
    second_draft = await _replace_debit_account(db, second_draft, account_id=health.id)
    await post_entry(db, second_draft, posted_by_id=user_id)

    memories = (await db.execute(select(Memory).where(Memory.tenant_id == tenant_id))).scalars().all()
    rules = _merchant_rule_rows(memories, "ShellX")

    assert len(rules) == 1
    assert rules[0].keywords == {"merchant": "shellx", "account_code": "5500"}
