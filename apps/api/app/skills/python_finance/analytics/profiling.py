from __future__ import annotations

import pandas as pd


def profile_records(records: list[dict]) -> dict:
    df = pd.DataFrame(records)
    if df.empty:
        return {"row_count": 0, "warnings": ["No records."]}

    profile: dict = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": list(df.columns),
        "missing_values": df.isna().sum().to_dict(),
        "duplicate_count": int(df.duplicated().sum()),
    }

    if "amount" in df.columns:
        amounts = pd.to_numeric(df["amount"], errors="coerce").dropna()
        profile["amount_distribution"] = {
            "min": float(amounts.min()) if len(amounts) else 0.0,
            "max": float(amounts.max()) if len(amounts) else 0.0,
            "mean": float(amounts.mean()) if len(amounts) else 0.0,
            "median": float(amounts.median()) if len(amounts) else 0.0,
        }

    if "date" in df.columns:
        dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        if len(dates):
            profile["date_range"] = {
                "start": str(dates.min().date()),
                "end": str(dates.max().date()),
            }

    return profile
