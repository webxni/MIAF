from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import FinClawError
from app.models import Account, AccountType, Memory, MemoryType, SourceTransaction
from app.services.audit import write_audit


def _category_to_code(text: str) -> str:
    normalized = text.lower()
    if any(token in normalized for token in ("gas", "gasolina", "uber", "lyft", "transport", "fuel")):
        return "5300"
    if any(token in normalized for token in ("food", "restaurant", "cafe", "coffee", "grocer", "dinner")):
        return "5200"
    if any(token in normalized for token in ("rent", "housing", "mortgage")):
        return "5100"
    if any(token in normalized for token in ("electric", "water", "utility", "internet")):
        return "5400"
    return "5900"


def _normalize_merchant(value: str | None) -> str:
    return (value or "").strip().lower()


def _source_text(tx: SourceTransaction) -> str:
    raw = tx.raw or {}
    memo = raw.get("memo") or raw.get("description") or ""
    return " ".join(part for part in ((tx.merchant or ""), memo) if part).strip().lower()


def _keyword_reason(text: str, code: str) -> str:
    keyword_map = {
        "5300": ("gas", "gasolina", "uber", "lyft", "transport", "fuel"),
        "5200": ("food", "restaurant", "cafe", "coffee", "grocer", "dinner"),
        "5100": ("rent", "housing", "mortgage"),
        "5400": ("electric", "water", "utility", "internet"),
    }
    for token in keyword_map.get(code, ()):
        if token in text:
            return f"keyword:{token}"
    return "default"


def classify_source_transaction(
    tx: SourceTransaction,
    accounts: list[Account],
    memory_lookup: Callable[[str], Account | None] | None = None,
) -> tuple[Account, str]:
    text = _source_text(tx)
    merchant = (tx.merchant or "").strip()
    expense_accounts = [account for account in accounts if account.type == AccountType.expense]
    if not expense_accounts:
        raise FinClawError("no_expense_account", code="no_expense_account")

    if memory_lookup is not None and merchant:
        remembered = memory_lookup(merchant)
        if remembered is not None:
            return remembered, "memory:merchant_rule"

    code = _category_to_code(text)
    reason = _keyword_reason(text, code)
    for account in expense_accounts:
        if account.code == code:
            return account, reason
    return expense_accounts[0], reason if code != "5900" else "default"


async def build_memory_lookup(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    accounts: list[Account],
) -> Callable[[str], Account | None]:
    rows = (
        await db.execute(
            select(Memory).where(
                Memory.tenant_id == tenant_id,
                Memory.memory_type == MemoryType.merchant_rule,
                Memory.is_active.is_(True),
                or_(Memory.entity_id == entity_id, Memory.entity_id.is_(None)),
            )
        )
    ).scalars().all()

    account_by_code = {account.code: account for account in accounts}
    rules: list[dict[str, str]] = []
    for row in rows:
        keywords = row.keywords if isinstance(row.keywords, dict) else {}
        merchant = _normalize_merchant(keywords.get("merchant"))
        account_code = str(keywords.get("account_code") or "").strip()
        summary = _normalize_merchant(row.summary)
        if merchant and account_code:
            rules.append(
                {
                    "merchant": merchant,
                    "account_code": account_code,
                    "summary": summary,
                }
            )

    def lookup(merchant: str) -> Account | None:
        normalized = _normalize_merchant(merchant)
        if not normalized:
            return None
        for rule in rules:
            rule_merchant = rule["merchant"]
            summary = rule["summary"]
            if (
                rule_merchant == normalized
                or rule_merchant in normalized
                or (summary and normalized in summary)
            ):
                return account_by_code.get(rule["account_code"])
        return None

    return lookup


async def record_merchant_correction(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_id: uuid.UUID,
    merchant: str,
    account: Account,
) -> Memory:
    normalized_merchant = _normalize_merchant(merchant)
    keywords = {
        "merchant": normalized_merchant,
        "account_code": account.code,
    }
    title = f"Merchant rule: {merchant}"
    summary = f"Use account {account.code} ({account.name}) for merchant '{merchant}'."

    existing = (
        await db.execute(
            select(Memory).where(
                Memory.tenant_id == tenant_id,
                Memory.entity_id == entity_id,
                Memory.memory_type == MemoryType.merchant_rule,
            )
        )
    ).scalars().all()
    memory = next(
        (
            row
            for row in existing
            if isinstance(row.keywords, dict) and _normalize_merchant(row.keywords.get("merchant")) == normalized_merchant
        ),
        None,
    )

    if memory is None:
        memory = Memory(
            tenant_id=tenant_id,
            user_id=user_id,
            entity_id=entity_id,
            memory_type=MemoryType.merchant_rule,
            title=title,
            content=summary,
            summary=summary,
            keywords=keywords,
            source="system",
            consent_granted=True,
            is_active=True,
        )
        db.add(memory)
    else:
        memory.user_id = user_id
        memory.title = title
        memory.content = summary
        memory.summary = summary
        memory.keywords = keywords
        memory.source = "system"
        memory.consent_granted = True
        memory.is_active = True

    await db.flush()
    await write_audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=entity_id,
        action="learn",
        object_type="memory",
        object_id=memory.id,
        after=keywords,
    )
    return memory
