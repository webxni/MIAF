from __future__ import annotations

import pandas as pd


def detect_amount_anomalies(
    records: list[dict],
    amount_col: str = "amount",
    group_col: str = "category",
    z_threshold: float = 2.5,
) -> dict:
    df = pd.DataFrame(records)
    if df.empty:
        return {"anomalies": [], "warnings": ["No records."]}

    if group_col not in df.columns:
        df[group_col] = "all"

    df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0.0).abs()

    def add_z_score(group: pd.DataFrame) -> pd.DataFrame:
        mean = group[amount_col].mean()
        std = group[amount_col].std()
        group = group.copy()
        group["z_score"] = 0.0 if not std or pd.isna(std) else (group[amount_col] - mean) / std
        return group

    scored = df.groupby(group_col, group_keys=False).apply(add_z_score)
    anomalies = scored[scored["z_score"].abs() >= z_threshold]

    questions = [
        {
            "record_id": row.get("id"),
            "question": f"Is this {row.get(group_col)} amount expected?",
            "reason": "Amount is unusual compared with similar records.",
        }
        for _, row in anomalies.iterrows()
    ]

    return {
        "anomalies": anomalies.to_dict("records"),
        "questions": questions,
    }
