from __future__ import annotations


def calculate_budget_summary(income: float, budget_lines: list[dict]) -> dict:
    total_budgeted = sum(float(line.get("amount", 0)) for line in budget_lines)
    remaining = income - total_budgeted

    by_type: dict[str, float] = {}
    for line in budget_lines:
        kind = line.get("type", "uncategorized")
        by_type[kind] = by_type.get(kind, 0.0) + float(line.get("amount", 0))

    return {
        "income": income,
        "total_budgeted": total_budgeted,
        "remaining": remaining,
        "by_type": by_type,
        "balanced": abs(remaining) < 0.01,
        "warnings": ["Budget exceeds income."] if remaining < 0 else [],
    }


def budget_variance(budget_lines: list[dict], actual_by_category: dict[str, float]) -> dict:
    rows = []
    for line in budget_lines:
        category = line["category"]
        budgeted = float(line.get("amount", 0))
        actual = float(actual_by_category.get(category, 0))
        remaining = budgeted - actual
        rows.append({
            "category": category,
            "budgeted": budgeted,
            "actual": actual,
            "remaining": remaining,
            "percent_used": actual / budgeted if budgeted else 0.0,
            "status": "overspent" if remaining < 0 else "ok",
        })
    return {"rows": rows, "overspent": [r for r in rows if r["status"] == "overspent"]}
