from __future__ import annotations

from collections.abc import Callable

from app.errors import FinClawError
from app.models import Account, AccountType, SourceTransaction
from app.services.agent import _category_to_code


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
    expense_accounts = [account for account in accounts if account.type == AccountType.expense]
    if not expense_accounts:
        raise FinClawError("no_expense_account", code="no_expense_account")

    if memory_lookup is not None:
        remembered = memory_lookup(text)
        if remembered is not None:
            return remembered, "memory"

    code = _category_to_code(text)
    reason = _keyword_reason(text, code)
    for account in expense_accounts:
        if account.code == code:
            return account, reason
    return expense_accounts[0], reason if code != "5900" else "default"
