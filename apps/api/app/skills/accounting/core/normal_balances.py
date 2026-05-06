from __future__ import annotations

NORMAL_BALANCE: dict[str, str] = {
    "asset": "debit",
    "expense": "debit",
    "contra_liability": "debit",
    "contra_equity": "debit",
    "contra_income": "debit",
    "liability": "credit",
    "equity": "credit",
    "income": "credit",
    "contra_asset": "credit",
    "contra_expense": "credit",
}


def account_effect(account_type: str, debit: float, credit: float) -> str:
    normal = NORMAL_BALANCE[account_type]
    if debit > 0:
        return "increase" if normal == "debit" else "decrease"
    if credit > 0:
        return "increase" if normal == "credit" else "decrease"
    return "no_effect"


def signed_balance(account_type: str, debit: float, credit: float) -> float:
    normal = NORMAL_BALANCE[account_type]
    return debit - credit if normal == "debit" else credit - debit
