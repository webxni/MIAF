from __future__ import annotations

import pandas as pd


def detect_lifestyle_creep(monthly: list[dict]) -> dict:
    df = pd.DataFrame(monthly)
    if len(df) < 3:
        return {"detected": False, "warnings": ["Need at least 3 months."]}

    income_start = df["income"].iloc[0]
    expense_start = df["expenses"].iloc[0]
    income_growth = df["income"].iloc[-1] / income_start - 1 if income_start else 0.0
    expense_growth = df["expenses"].iloc[-1] / expense_start - 1 if expense_start else 0.0
    savings_rate_change = float(df["savings_rate"].iloc[-1] - df["savings_rate"].iloc[0])

    detected = bool(expense_growth > income_growth and savings_rate_change <= 0)
    return {
        "detected": detected,
        "income_growth": float(income_growth),
        "expense_growth": float(expense_growth),
        "savings_rate_change": savings_rate_change,
    }
