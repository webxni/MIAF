from __future__ import annotations

import numpy as np


def simulate_goal_balance(
    starting_balance: float,
    monthly_contribution: float,
    months: int,
    expected_monthly_return: float = 0.0,
    monthly_volatility: float = 0.0,
    simulations: int = 1000,
    goal_amount: float | None = None,
    seed: int = 42,
) -> dict:
    if months <= 0:
        raise ValueError("months must be positive")
    if simulations <= 0:
        raise ValueError("simulations must be positive")

    rng = np.random.default_rng(seed)
    balances = np.zeros((simulations, months + 1))
    balances[:, 0] = starting_balance

    for month in range(1, months + 1):
        random_returns = rng.normal(expected_monthly_return, monthly_volatility, simulations)
        balances[:, month] = balances[:, month - 1] * (1 + random_returns) + monthly_contribution
        balances[:, month] = np.maximum(balances[:, month], 0.0)

    ending = balances[:, -1]
    result: dict = {
        "ending_balance_percentiles": {
            "p10": float(np.percentile(ending, 10)),
            "p25": float(np.percentile(ending, 25)),
            "p50": float(np.percentile(ending, 50)),
            "p75": float(np.percentile(ending, 75)),
            "p90": float(np.percentile(ending, 90)),
        },
        "assumptions": {
            "starting_balance": starting_balance,
            "monthly_contribution": monthly_contribution,
            "months": months,
            "expected_monthly_return": expected_monthly_return,
            "monthly_volatility": monthly_volatility,
            "simulations": simulations,
        },
        "limitations": [
            "This is a hypothetical simulation.",
            "Results are not guaranteed.",
            "Assumptions may be wrong.",
        ],
    }
    if goal_amount is not None:
        result["success_probability"] = float((ending >= goal_amount).mean())
    return result
