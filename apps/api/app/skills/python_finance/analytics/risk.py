from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_max_drawdown_from_returns(returns: pd.Series) -> float:
    cumulative = (1 + returns.fillna(0)).cumprod()
    running_peak = cumulative.cummax()
    drawdown = cumulative / running_peak - 1
    return float(drawdown.min())


def calculate_historical_var(
    returns: list[float],
    confidence_level: float = 0.95,
    portfolio_value: float | None = None,
) -> dict:
    clean = pd.Series(returns).dropna()
    if clean.empty:
        return {"warnings": ["No returns available."]}

    percentile = (1 - confidence_level) * 100
    var_percent = float(np.percentile(clean, percentile))
    result: dict = {
        "confidence_level": confidence_level,
        "var_percent": var_percent,
        "method": "historical",
        "limitations": [
            "Historical VaR is based on past returns.",
            "It is an estimate, not a guarantee.",
            "It does not predict worst-case loss.",
        ],
    }
    if portfolio_value is not None:
        result["var_amount"] = float(abs(var_percent) * portfolio_value)
    return result


def calculate_risk_metrics(
    returns: list[float],
    confidence_level: float = 0.95,
) -> dict:
    r = pd.Series(returns).dropna()
    if r.empty:
        return {"warnings": ["No returns available."]}

    downside = r[r < 0]
    var_result = calculate_historical_var(r.tolist(), confidence_level)
    return {
        "mean_return": float(r.mean()),
        "standard_deviation": float(r.std()),
        "downside_deviation": float(downside.std()) if len(downside) else 0.0,
        "historical_var": var_result.get("var_percent"),
        "max_drawdown": calculate_max_drawdown_from_returns(r),
        "best_period": float(r.max()),
        "worst_period": float(r.min()),
        "positive_period_ratio": float((r > 0).mean()),
        "limitations": var_result.get("limitations", []),
    }
