from __future__ import annotations


def straight_line_depreciation(
    cost: float,
    salvage_value: float,
    useful_life_months: int,
) -> dict:
    if useful_life_months <= 0:
        raise ValueError("useful_life_months must be positive")

    depreciable_base = max(cost - salvage_value, 0.0)
    monthly_depreciation = depreciable_base / useful_life_months

    return {
        "cost": cost,
        "salvage_value": salvage_value,
        "useful_life_months": useful_life_months,
        "depreciable_base": depreciable_base,
        "monthly_depreciation": round(monthly_depreciation, 2),
        "annual_depreciation": round(monthly_depreciation * 12, 2),
    }
