from __future__ import annotations

import pandas as pd

from app.skills.accounting.core.normal_balances import NORMAL_BALANCE


def build_general_ledger(journal_lines: list[dict], accounts: list[dict]) -> dict:
    lines = pd.DataFrame(journal_lines)
    acct = pd.DataFrame(accounts)

    if lines.empty:
        return {"accounts": [], "warnings": ["No journal lines."]}

    df = lines.merge(acct, left_on="account_id", right_on="id", how="left")
    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)

    ledgers = []
    for account_id, group in df.groupby("account_id"):
        account_type = group["type"].iloc[0]
        normal = NORMAL_BALANCE.get(account_type, "debit")
        group = group.copy()

        if normal == "debit":
            group["signed_amount"] = group["debit"] - group["credit"]
        else:
            group["signed_amount"] = group["credit"] - group["debit"]

        group = group.sort_values("date")
        group["running_balance"] = group["signed_amount"].cumsum()

        ledgers.append({
            "account_id": account_id,
            "account_name": group["name"].iloc[0],
            "account_type": account_type,
            "normal_balance": normal,
            "ending_balance": float(group["running_balance"].iloc[-1]),
            "lines": group.to_dict("records"),
        })

    return {"accounts": ledgers}
