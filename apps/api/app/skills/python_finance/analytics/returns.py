from __future__ import annotations

import numpy as np

from app.skills.python_finance.core.dataframes import clean_financial_records, dataframe_to_records


def calculate_returns(
    observations: list[dict],
    value_col: str = "value",
    date_col: str = "date",
    periods_per_year: int = 252,
) -> dict:
    df = clean_financial_records(observations, date_col, value_col)
    if len(df) < 2:
        return {"series": [], "summary": {}, "warnings": ["Need at least two observations."]}

    df = df.copy()
    df["simple_return"] = df[value_col].pct_change()
    df["log_return"] = np.log(df[value_col] / df[value_col].shift(1))

    valid = df["log_return"].dropna()
    cumulative_return = df[value_col].iloc[-1] / df[value_col].iloc[0] - 1

    return {
        "series": dataframe_to_records(df),
        "summary": {
            "cumulative_return": float(cumulative_return),
            "annualized_return": float(valid.mean() * periods_per_year),
            "annualized_volatility": float(valid.std() * np.sqrt(periods_per_year)),
            "observations": int(len(df)),
        },
    }
