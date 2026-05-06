from __future__ import annotations

import numpy as np

from app.skills.python_finance.core.dataframes import clean_financial_records, dataframe_to_records


def calculate_rolling_statistics(
    observations: list[dict],
    value_col: str = "value",
    date_col: str = "date",
    window: int = 30,
    annualization_factor: int | None = None,
) -> dict:
    df = clean_financial_records(observations, date_col, value_col)
    if df.empty:
        return {"series": [], "warnings": ["No data."]}

    df = df.copy()
    df["rolling_mean"] = df[value_col].rolling(window).mean()
    df["rolling_std"] = df[value_col].rolling(window).std()
    df["rolling_min"] = df[value_col].rolling(window).min()
    df["rolling_max"] = df[value_col].rolling(window).max()

    if annualization_factor:
        df["rolling_volatility"] = df["rolling_std"] * np.sqrt(annualization_factor)

    return {"series": dataframe_to_records(df), "window": window}
