from __future__ import annotations

import pandas as pd


def analyze_spending_habits(transactions: list[dict]) -> dict:
    df = pd.DataFrame(transactions)
    if df.empty:
        return {"patterns": [], "questions": []}

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0).abs()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["day_of_week"] = df["date"].dt.day_name()

    top_merchants: list[dict] = []
    if "merchant" in df.columns:
        top_merchants = (
            df.groupby("merchant")["amount"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
            .to_dict("records")
        )

    top_categories: list[dict] = []
    if "category" in df.columns:
        top_categories = (
            df.groupby("category")["amount"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
            .to_dict("records")
        )

    questions: list[str] = []
    if top_merchants:
        merchant = top_merchants[0]["merchant"]
        questions.append(f"Do you want me to watch spending at {merchant} more closely?")

    return {
        "top_merchants": top_merchants,
        "top_categories": top_categories,
        "questions": questions,
    }
