from __future__ import annotations

import pandas as pd


def calculate_personal_cashflow(transactions: list[dict]) -> dict:
    df = pd.DataFrame(transactions)
    if df.empty:
        return {
            "income": 0.0,
            "expenses": 0.0,
            "net_cashflow": 0.0,
            "savings_rate": 0.0,
            "warnings": ["No transactions available."],
        }

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    income = float(df[df["type"] == "income"]["amount"].sum())
    expenses = float(df[df["type"] == "expense"]["amount"].abs().sum())
    net_cashflow = income - expenses
    savings_rate = net_cashflow / income if income > 0 else 0.0

    return {
        "income": income,
        "expenses": expenses,
        "net_cashflow": net_cashflow,
        "savings_rate": savings_rate,
    }
