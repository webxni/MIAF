from __future__ import annotations

import pandas as pd


def calculate_ar_aging(invoices: list[dict], as_of_date: str) -> dict:
    df = pd.DataFrame(invoices)
    if df.empty:
        return {"buckets": {}, "rows": []}

    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
    df["open_amount"] = pd.to_numeric(df["open_amount"], errors="coerce").fillna(0.0)
    as_of = pd.to_datetime(as_of_date)
    df["days_past_due"] = (as_of - df["due_date"]).dt.days

    def bucket(days: int) -> str:
        if days <= 0:
            return "current"
        if days <= 30:
            return "1_30"
        if days <= 60:
            return "31_60"
        if days <= 90:
            return "61_90"
        return "90_plus"

    df["bucket"] = df["days_past_due"].apply(bucket)
    buckets = df.groupby("bucket")["open_amount"].sum().to_dict()
    return {"buckets": buckets, "rows": df.to_dict("records")}
