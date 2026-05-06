from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

import numpy as np
import pandas as pd


def to_dataframe(records: list[dict] | None) -> pd.DataFrame:
    if records is None:
        return pd.DataFrame()
    if not isinstance(records, list):
        raise ValueError("records must be a list of dictionaries")
    return pd.DataFrame(records)


def require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def normalize_amount_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def normalize_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def clean_financial_records(
    records: list[dict],
    date_col: str = "date",
    amount_col: str = "amount",
) -> pd.DataFrame:
    df = to_dataframe(records)
    if df.empty:
        return df
    require_columns(df, [date_col, amount_col])
    df = df.copy()
    df[date_col] = normalize_date_series(df[date_col])
    df[amount_col] = normalize_amount_series(df[amount_col])
    df = df.dropna(subset=[date_col, amount_col])
    return df.sort_values(date_col)


def decimal_money(value: float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def replace_non_finite(value):
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return value


def dataframe_to_records(df: pd.DataFrame) -> list[dict]:
    safe = df.replace([np.inf, -np.inf], np.nan)
    records = safe.to_dict("records")
    return [
        {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in row.items()}
        for row in records
    ]
