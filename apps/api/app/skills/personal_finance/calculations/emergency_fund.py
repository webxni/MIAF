from __future__ import annotations


def emergency_fund_plan(
    monthly_essential_expenses: float,
    current_fund: float,
    target_months: int = 6,
    monthly_contribution: float = 0.0,
) -> dict:
    target = monthly_essential_expenses * target_months
    gap = max(target - current_fund, 0.0)
    months_covered = (
        current_fund / monthly_essential_expenses if monthly_essential_expenses else 0.0
    )
    months_to_goal = gap / monthly_contribution if monthly_contribution > 0 else None

    return {
        "target": target,
        "current_fund": current_fund,
        "gap": gap,
        "months_covered": months_covered,
        "monthly_contribution": monthly_contribution,
        "months_to_goal": months_to_goal,
    }
