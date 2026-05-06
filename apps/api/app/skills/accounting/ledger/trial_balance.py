from __future__ import annotations

import pandas as pd


def generate_trial_balance(journal_lines: list[dict], accounts: list[dict]) -> dict:
    lines = pd.DataFrame(journal_lines)
    acct = pd.DataFrame(accounts)

    if lines.empty:
        return {"rows": [], "balanced": True, "total_debits": 0.0, "total_credits": 0.0}

    df = lines.merge(acct, left_on="account_id", right_on="id", how="left")
    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)

    grouped = (
        df.groupby(["account_id", "code", "name", "type"])[["debit", "credit"]]
        .sum()
        .reset_index()
    )

    rows = []
    total_debits = 0.0
    total_credits = 0.0

    for _, row in grouped.iterrows():
        balance = float(row["debit"] - row["credit"])
        debit_balance = balance if balance >= 0 else 0.0
        credit_balance = abs(balance) if balance < 0 else 0.0
        total_debits += debit_balance
        total_credits += credit_balance

        rows.append({
            "account_id": row["account_id"],
            "code": row["code"],
            "name": row["name"],
            "type": row["type"],
            "debit_balance": round(debit_balance, 2),
            "credit_balance": round(credit_balance, 2),
        })

    return {
        "rows": rows,
        "total_debits": round(total_debits, 2),
        "total_credits": round(total_credits, 2),
        "balanced": round(total_debits, 2) == round(total_credits, 2),
    }
