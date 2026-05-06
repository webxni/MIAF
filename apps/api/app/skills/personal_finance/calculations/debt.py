from __future__ import annotations


def choose_debt_strategy(user_preference: str, debts: list[dict]) -> dict:
    if user_preference == "motivation":
        strategy = "snowball"
        sort_key = lambda d: float(d.get("balance", 0))
    elif user_preference == "interest":
        strategy = "avalanche"
        sort_key = lambda d: -float(d.get("interest_rate", 0))
    else:
        strategy = "cashflow_relief"
        sort_key = lambda d: -float(d.get("minimum_payment", 0))

    ordered = sorted(debts, key=sort_key)
    return {
        "strategy": strategy,
        "ordered_debts": [
            {**debt, "priority": index + 1}
            for index, debt in enumerate(ordered)
        ],
    }
