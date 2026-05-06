from __future__ import annotations

import pandas as pd

from app.skills.python_finance.core.dataframes import clean_financial_records, dataframe_to_records


def analyze_time_series(
    observations: list[dict],
    value_col: str = "value",
    date_col: str = "date",
    frequency: str = "ME",
    aggregation: str = "sum",
) -> dict:
    df = clean_financial_records(observations, date_col, value_col)
    if df.empty:
        return {"series": [], "warnings": ["No valid time series data."]}

    ts = df.set_index(date_col)[value_col].sort_index()

    if aggregation == "sum":
        resampled = ts.resample(frequency).sum()
    elif aggregation == "mean":
        resampled = ts.resample(frequency).mean()
    elif aggregation == "last":
        resampled = ts.resample(frequency).last()
    else:
        raise ValueError("aggregation must be sum, mean, or last")

    out = pd.DataFrame({"period": resampled.index.astype(str), "value": resampled.values})
    out["change"] = out["value"].diff()
    out["pct_change"] = out["value"].pct_change()

    return {
        "series": dataframe_to_records(out),
        "summary": {
            "start": str(ts.index.min().date()),
            "end": str(ts.index.max().date()),
            "periods": int(len(out)),
            "total": float(resampled.sum()),
            "average": float(resampled.mean()),
            "latest": float(resampled.iloc[-1]) if len(resampled) else 0.0,
        },
    }
