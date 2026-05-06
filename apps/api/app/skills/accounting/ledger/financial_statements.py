from __future__ import annotations

import pandas as pd

from app.skills.accounting.core.normal_balances import NORMAL_BALANCE


def generate_income_statement(journal_lines: list[dict], accounts: list[dict]) -> dict:
    lines = pd.DataFrame(journal_lines)
    acct = pd.DataFrame(accounts)
    if lines.empty:
        return {
            "revenue": 0.0,
            "expenses": 0.0,
            "net_income": 0.0,
            "warnings": ["No ledger data."],
        }

    df = lines.merge(acct, left_on="account_id", right_on="id", how="left")
    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)

    income_df = df[df["type"] == "income"].copy()
    expense_df = df[df["type"] == "expense"].copy()

    revenue = float((income_df["credit"] - income_df["debit"]).sum())
    expenses = float((expense_df["debit"] - expense_df["credit"]).sum())
    net_income = revenue - expenses

    expenses_by_account = (
        expense_df.assign(amount=expense_df["debit"] - expense_df["credit"])
        .groupby("name")["amount"]
        .sum()
        .reset_index()
        .sort_values("amount", ascending=False)
        .to_dict("records")
    )

    return {
        "revenue": revenue,
        "expenses": expenses,
        "net_income": net_income,
        "expenses_by_account": expenses_by_account,
    }


def generate_balance_sheet(journal_lines: list[dict], accounts: list[dict]) -> dict:
    lines = pd.DataFrame(journal_lines)
    acct = pd.DataFrame(accounts)
    if lines.empty:
        return {"assets": 0.0, "liabilities": 0.0, "equity": 0.0, "balanced": True}

    df = lines.merge(acct, left_on="account_id", right_on="id", how="left")
    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)

    def signed(row: pd.Series) -> float:
        normal = NORMAL_BALANCE.get(row["type"], "debit")
        return float(row["debit"] - row["credit"]) if normal == "debit" else float(row["credit"] - row["debit"])

    df["balance"] = df.apply(signed, axis=1)

    assets = float(df[df["type"] == "asset"]["balance"].sum())
    liabilities = float(df[df["type"] == "liability"]["balance"].sum())
    equity = float(df[df["type"] == "equity"]["balance"].sum())

    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "balanced": round(assets, 2) == round(liabilities + equity, 2),
        "difference": round(assets - liabilities - equity, 2),
    }
