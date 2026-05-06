from __future__ import annotations


def calculate_room_for_error_score(profile: dict) -> dict:
    score = 100
    issues: list[str] = []

    if profile.get("emergency_fund_months", 0) < 3:
        score -= 25
        issues.append("Emergency fund below 3 months.")

    if profile.get("debt_to_income_ratio", 0) > 0.35:
        score -= 20
        issues.append("Debt-to-income ratio is high.")

    if profile.get("business_income_dependency", 0) > 0.75:
        score -= 15
        issues.append("Personal income depends heavily on business cashflow.")

    if profile.get("tax_reserve_gap", 0) > 0:
        score -= 15
        issues.append("Tax reserve may be underfunded.")

    score = max(score, 0)
    return {
        "score": score,
        "issues": issues,
        "risk_level": "low" if score >= 75 else "medium" if score >= 50 else "high",
    }
