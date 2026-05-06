from __future__ import annotations

import pandas as pd


def identify_subscription_candidates(transactions: list[dict]) -> dict:
    df = pd.DataFrame(transactions)
    if df.empty or "merchant" not in df.columns:
        return {"subscriptions": []}

    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0).abs()

    candidates = []
    for merchant, group in df.groupby("merchant"):
        if len(group) >= 3:
            amount_std = group["amount"].std()
            avg_amount = group["amount"].mean()
            if avg_amount and (pd.isna(amount_std) or amount_std / avg_amount < 0.10):
                candidates.append({
                    "merchant": merchant,
                    "average_amount": float(avg_amount),
                    "occurrences": int(len(group)),
                    "question": f"Do you still use {merchant} enough to keep paying for it?",
                })

    return {"subscriptions": candidates}
