from __future__ import annotations

import pandas as pd


def calculate_portfolio_allocation(
    holdings: list[dict],
    group_col: str = "asset_class",
    value_col: str = "market_value",
    target_allocation: dict[str, float] | None = None,
    concentration_threshold: float = 0.25,
) -> dict:
    df = pd.DataFrame(holdings)
    if df.empty:
        return {"allocation": [], "warnings": ["No holdings."]}

    df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0.0)
    total = df[value_col].sum()
    if total <= 0:
        return {"allocation": [], "warnings": ["Total market value is zero."]}

    grouped = (
        df.groupby(group_col)[value_col]
        .sum()
        .reset_index()
        .rename(columns={value_col: "market_value"})
    )
    grouped["percentage"] = grouped["market_value"] / total

    drift: list[dict] = []
    if target_allocation:
        for _, row in grouped.iterrows():
            label = row[group_col]
            actual = float(row["percentage"])
            target = float(target_allocation.get(label, 0.0))
            drift.append({
                group_col: label,
                "target": target,
                "actual": actual,
                "drift": actual - target,
            })

    concentration = grouped[grouped["percentage"] > concentration_threshold].to_dict("records")

    return {
        "total_market_value": float(total),
        "allocation": grouped.to_dict("records"),
        "target_drift": drift,
        "concentration_warnings": concentration,
        "safety_note": "Educational allocation analysis only. No trades are executed.",
    }
