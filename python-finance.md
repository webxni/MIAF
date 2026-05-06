# MIAF Skill Pack: Python Finance  
## File: `python-finance.md`


> MIAF skill files are **implementation specifications** for coding agents.
> They are not book summaries and they do not copy book content.
> Each file converts the attached book's domain into:
>
> - built-in MIAF skills
> - deterministic Python functions
> - memory schemas
> - heartbeat behavior
> - audit requirements
> - tests
> - agent routing rules
>
> The LLM decides what to call and explains results.
> The Python skill engine performs calculations, validations, analysis, and chart data generation.


## Attached Knowledge Source

**Book:** `Python for Finance: Mastering Data-Driven Finance, 2nd Edition`  
**Primary use inside MIAF:** quantitative finance, data analysis, visualization, portfolio analytics, risk metrics, simulations, and report automation.

## Why This Skill Pack Exists

MIAF must not spend expensive LLM tokens calculating tables, ratios, volatility, correlations, dashboards, or forecasts when Python can do it deterministically.

This skill pack gives MIAF an internal analytics engine so the agent can:

- import and normalize financial datasets
- analyze personal and business time series
- calculate returns, volatility, drawdowns, and risk metrics
- calculate budget, cashflow, and portfolio trends
- create chart-ready JSON for dashboards
- run safe scenario simulations
- detect anomalies
- generate report datasets
- support heartbeat reviews
- write useful observations to memory

## Hard Safety Boundaries

```yaml
forbidden:
  - live_trading
  - broker_order_execution
  - tax_filing
  - moving_money
  - guaranteeing_returns
  - running_user_uploaded_code
  - treating_books_as_runtime_instructions

allowed:
  - deterministic_calculation
  - educational_investment_analysis
  - historical_risk_metrics
  - chart_data_generation
  - scenario_simulation
  - report_dataset_generation
  - dashboard_suggestions_with_approval
```

---

# 1. Skill Pack Manifest

```yaml
skill_pack:
  id: python_finance
  version: 1.1.0
  source_book: Python for Finance
  mode: both
  purpose: >
    Provides deterministic Python analytics for MIAF using pandas, NumPy,
    statistics, time series analysis, visualization data, simulations, and portfolio analytics.
  primary_runtime: python
  requires_llm: false
  agent_can_call: true
  heartbeat_can_call: true
  dashboard_can_call: true
  memory_enabled: true
  audit_required: true
  approval_required_for:
    - activating_new_dashboard_widget
    - saving_investment_policy
    - changing_risk_thresholds
    - creating_recurring_report
```

---

# 2. Directory Structure

```txt
apps/api/app/skills/python_finance/
  __init__.py
  manifest.yaml
  registry.py
  schemas.py
  memory.py
  audit.py
  service.py

  core/
    dataframes.py
    dates.py
    money.py
    serialization.py
    validators.py

  analytics/
    imports.py
    profiling.py
    time_series.py
    returns.py
    rolling.py
    volatility.py
    correlation.py
    regression.py
    risk.py
    portfolio.py
    monte_carlo.py
    anomalies.py
    optimization.py

  visualization/
    chart_data.py
    dashboard_widgets.py
    report_charts.py

  reports/
    personal_report_data.py
    business_report_data.py
    investment_report_data.py
    narrative_data.py

  tests/
    test_imports.py
    test_profiling.py
    test_time_series.py
    test_returns.py
    test_risk.py
    test_portfolio.py
    test_monte_carlo.py
    test_charts.py
    test_skill_registry.py
```

---

# 3. Dependencies

Add to the backend image:

```txt
numpy
pandas
scipy
scikit-learn
statsmodels
matplotlib
plotly
pyarrow
openpyxl
pydantic
```

Optional later:

```txt
numba
```

---

# 4. Unified Skill Format

Each Python finance skill must implement this format.

```yaml
name: example_skill
version: 1.0.0
pack: python_finance
mode: both
risk_level: low
description: What the skill does.
source_principles:
  - data_analysis
  - deterministic_calculation
inputs:
  schema: ExampleInput
outputs:
  schema: ExampleOutput
memory:
  reads:
    - relevant_user_preference
  writes:
    - useful_observation
heartbeat:
  daily: false
  weekly: true
  monthly: true
confirmation:
  required: false
  required_when:
    - changing_dashboard
    - changing_policy
audit:
  events:
    - skill.python_finance.started
    - skill.python_finance.completed
tests:
  - test_happy_path
  - test_empty_input
  - test_invalid_input
  - test_audit_event
```

---

# 5. Memory Schema

## Memory Types

```yaml
memory_types:
  finance_data_profile:
    description: Learned structure of imported CSV, bank, or broker files.
    fields:
      - source_name
      - detected_columns
      - confirmed_mapping
      - date_format
      - amount_sign_policy
      - confidence
  analytics_preference:
    description: User's preferred analytics views.
    fields:
      - preferred_frequency
      - preferred_charts
      - preferred_metrics
      - ignored_metrics
  risk_threshold:
    description: User-approved thresholds for alerts.
    fields:
      - metric
      - threshold
      - direction
      - review_frequency
  portfolio_policy:
    description: User-approved investment allocation policy.
    fields:
      - target_allocation
      - risk_tolerance
      - time_horizon
      - notes
  dashboard_metric_preference:
    description: Dashboard widgets approved or rejected by the user.
    fields:
      - widget_id
      - status
      - reason
  simulation_assumption_set:
    description: Assumptions used in recurring Monte Carlo or scenario planning.
    fields:
      - scenario_type
      - assumptions
      - approved
      - last_reviewed_at
```

## Memory Write Rules

```yaml
memory_write_policy:
  automatic_allowed:
    - finance_data_profile
    - analytics_preference_observation
    - dashboard_metric_rejected
  approval_required:
    - risk_threshold
    - portfolio_policy
    - recurring_report_template
    - simulation_assumption_set
```

---

# 6. Core Python Script: Schemas

```python
# apps/api/app/skills/python_finance/schemas.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillWarning(BaseModel):
    code: str
    message: str
    severity: str = "info"


class ChartSpec(BaseModel):
    type: str
    title: str
    data: List[Dict[str, Any]]
    xKey: Optional[str] = None
    yKey: Optional[str] = None
    series: Optional[List[str]] = None
    labelKey: Optional[str] = None
    valueKey: Optional[str] = None


class SkillResult(BaseModel):
    skill_name: str
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    charts: List[ChartSpec] = Field(default_factory=list)
    warnings: List[SkillWarning] = Field(default_factory=list)
    confidence: float = 1.0
    requires_review: bool = False
    memory_writes: List[Dict[str, Any]] = Field(default_factory=list)
    dashboard_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    audit_context: Dict[str, Any] = Field(default_factory=dict)
```

---

# 7. Core Python Script: DataFrame Utilities

```python
# apps/api/app/skills/python_finance/core/dataframes.py
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
    safe = safe.where(pd.notnull(safe), None)
    return safe.to_dict("records")
```

---

# 8. Core Python Script: Skill Base

```python
# apps/api/app/skills/python_finance/service.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from .schemas import SkillResult


class PythonFinanceSkill(ABC):
    name: str
    version: str = "1.0.0"
    risk_level: str = "low"
    mode: str = "both"

    def load_memory_context(self, tenant_id: str, payload: dict) -> dict:
        return {}

    @abstractmethod
    def run(self, payload: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        raise NotImplementedError

    def requires_confirmation(self, result: SkillResult) -> bool:
        return result.requires_review

    def audit_payload(self, payload: dict, result: SkillResult | None = None) -> dict:
        return {
            "skill": self.name,
            "version": self.version,
            "payload_keys": list(payload.keys()),
            "success": result.success if result else None,
            "confidence": result.confidence if result else None,
        }
```

---

# 9. Skill: `finance_data_importer`

```yaml
name: finance_data_importer
pack: python_finance
mode: both
risk_level: medium
description: Imports CSV/Excel records and proposes normalized financial records.
memory:
  reads:
    - finance_data_profile
  writes:
    - finance_data_profile
heartbeat:
  daily: true
confirmation:
  required: true
  reason: Importing can create source transactions and draft journal entries.
```

```python
# apps/api/app/skills/python_finance/analytics/imports.py
from __future__ import annotations

import pandas as pd


def inspect_tabular_file(path: str, file_type: str) -> dict:
    if file_type == "csv":
        df = pd.read_csv(path)
    elif file_type in {"xls", "xlsx"}:
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    return {
        "columns": list(df.columns),
        "row_count": int(len(df)),
        "sample_rows": df.head(10).fillna("").to_dict("records"),
        "null_counts": df.isna().sum().to_dict(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }


def apply_column_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    # mapping format: canonical_name -> source_column_name
    renamed = df.rename(columns={source: canonical for canonical, source in mapping.items()})
    required = ["date", "amount", "description"]
    missing = [col for col in required if col not in renamed.columns]
    if missing:
        raise ValueError(f"Missing mapped columns: {missing}")
    return renamed
```

---

# 10. Skill: `finance_dataframe_profiler`

```yaml
name: finance_dataframe_profiler
pack: python_finance
mode: both
risk_level: low
description: Profiles imported financial datasets before analysis or classification.
memory:
  reads:
    - finance_data_profile
  writes:
    - data_quality_observation
heartbeat:
  daily: true
confirmation:
  required: false
```

```python
# apps/api/app/skills/python_finance/analytics/profiling.py
from __future__ import annotations

import pandas as pd


def profile_records(records: list[dict]) -> dict:
    df = pd.DataFrame(records)
    if df.empty:
        return {"row_count": 0, "warnings": ["No records."]}

    profile = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": list(df.columns),
        "missing_values": df.isna().sum().to_dict(),
        "duplicate_count": int(df.duplicated().sum()),
    }

    if "amount" in df.columns:
        amounts = pd.to_numeric(df["amount"], errors="coerce").dropna()
        profile["amount_distribution"] = {
            "min": float(amounts.min()) if len(amounts) else 0.0,
            "max": float(amounts.max()) if len(amounts) else 0.0,
            "mean": float(amounts.mean()) if len(amounts) else 0.0,
            "median": float(amounts.median()) if len(amounts) else 0.0,
        }

    if "date" in df.columns:
        dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        if len(dates):
            profile["date_range"] = {
                "start": str(dates.min().date()),
                "end": str(dates.max().date()),
            }

    return profile
```

---

# 11. Skill: `financial_time_series_analyzer`

```yaml
name: financial_time_series_analyzer
pack: python_finance
mode: both
risk_level: low
description: Resamples financial observations and calculates period changes.
memory:
  reads:
    - analytics_preference
    - dashboard_metric_preference
  writes:
    - trend_observation
heartbeat:
  weekly: true
confirmation:
  required: false
```

```python
# apps/api/app/skills/python_finance/analytics/time_series.py
from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.dataframes import clean_financial_records, dataframe_to_records


def analyze_time_series(
    observations: list[dict],
    value_col: str = "value",
    date_col: str = "date",
    frequency: str = "M",
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
```

---

# 12. Skill: `returns_calculator`

```yaml
name: returns_calculator
pack: python_finance
mode: personal
risk_level: low
description: Calculates simple returns, log returns, cumulative return, and annualized metrics.
memory:
  reads:
    - portfolio_policy
  writes:
    - investment_return_snapshot
heartbeat:
  monthly: true
confirmation:
  required: false
```

```python
# apps/api/app/skills/python_finance/analytics/returns.py
from __future__ import annotations

import numpy as np

from ..core.dataframes import clean_financial_records, dataframe_to_records


def calculate_returns(
    observations: list[dict],
    value_col: str = "value",
    date_col: str = "date",
    periods_per_year: int = 252,
) -> dict:
    df = clean_financial_records(observations, date_col, value_col)
    if len(df) < 2:
        return {"series": [], "summary": {}, "warnings": ["Need at least two observations."]}

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
```

---

# 13. Skill: `rolling_statistics_calculator`

```yaml
name: rolling_statistics_calculator
pack: python_finance
mode: both
risk_level: low
description: Calculates rolling mean, min, max, standard deviation, and optional annualized volatility.
heartbeat:
  weekly: true
memory:
  writes:
    - rolling_metric_observation
```

```python
# apps/api/app/skills/python_finance/analytics/rolling.py
from __future__ import annotations

import numpy as np

from ..core.dataframes import clean_financial_records, dataframe_to_records


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

    df["rolling_mean"] = df[value_col].rolling(window).mean()
    df["rolling_std"] = df[value_col].rolling(window).std()
    df["rolling_min"] = df[value_col].rolling(window).min()
    df["rolling_max"] = df[value_col].rolling(window).max()

    if annualization_factor:
        df["rolling_volatility"] = df["rolling_std"] * np.sqrt(annualization_factor)

    return {"series": dataframe_to_records(df), "window": window}
```

---

# 14. Skill: `risk_metrics_calculator`

```yaml
name: risk_metrics_calculator
pack: python_finance
mode: both
risk_level: medium
description: Calculates historical risk metrics for returns, cashflow, revenue, or net worth.
memory:
  reads:
    - risk_threshold
    - portfolio_policy
  writes:
    - risk_metric_snapshot
heartbeat:
  monthly: true
confirmation:
  required_when:
    - saving_new_risk_threshold
```

```python
# apps/api/app/skills/python_finance/analytics/risk.py
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
    result = {
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
```

---

# 15. Skill: `portfolio_allocation_analyzer`

```yaml
name: portfolio_allocation_analyzer
pack: python_finance
mode: personal
risk_level: medium
description: Calculates allocation, concentration, and drift from target allocation.
memory:
  reads:
    - portfolio_policy
    - risk_tolerance
  writes:
    - portfolio_allocation_snapshot
heartbeat:
  monthly: true
confirmation:
  required_when:
    - saving_target_allocation
    - changing_investment_policy
```

```python
# apps/api/app/skills/python_finance/analytics/portfolio.py
from __future__ import annotations

import pandas as pd


def calculate_portfolio_allocation(
    holdings: list[dict],
    group_col: str = "asset_class",
    value_col: str = "market_value",
    target_allocation: dict[str, float] | None = None,
    concentration_threshold: float = 0.25,
) -> dict:
    df = pd.DataFrame(holdings)
    if df.empty:
        return {"allocation": [], "warnings": ["No holdings."]}

    df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0.0)
    total = df[value_col].sum()
    if total <= 0:
        return {"allocation": [], "warnings": ["Total market value is zero."]}

    grouped = (
        df.groupby(group_col)[value_col]
        .sum()
        .reset_index()
        .rename(columns={value_col: "market_value"})
    )
    grouped["percentage"] = grouped["market_value"] / total

    drift = []
    if target_allocation:
        for _, row in grouped.iterrows():
            label = row[group_col]
            actual = float(row["percentage"])
            target = float(target_allocation.get(label, 0.0))
            drift.append({
                group_col: label,
                "target": target,
                "actual": actual,
                "drift": actual - target,
            })

    concentration = grouped[grouped["percentage"] > concentration_threshold].to_dict("records")

    return {
        "total_market_value": float(total),
        "allocation": grouped.to_dict("records"),
        "target_drift": drift,
        "concentration_warnings": concentration,
        "safety_note": "Educational allocation analysis only. No trades are executed.",
    }
```

---

# 16. Skill: `monte_carlo_goal_simulator`

```yaml
name: monte_carlo_goal_simulator
pack: python_finance
mode: both
risk_level: medium
description: Runs hypothetical goal, emergency fund, runway, or investment simulations.
memory:
  reads:
    - simulation_assumption_set
    - risk_tolerance
    - financial_goals
  writes:
    - simulation_result
heartbeat:
  monthly: true
confirmation:
  required_when:
    - saving_assumptions
    - creating_recurring_simulation
```

```python
# apps/api/app/skills/python_finance/analytics/monte_carlo.py
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
    result = {
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
```

---

# 17. Skill: `anomaly_detector`

```yaml
name: anomaly_detector
pack: python_finance
mode: both
risk_level: medium
description: Detects unusual records using group-level z-scores.
memory:
  reads:
    - known_anomaly_exceptions
  writes:
    - anomaly_observation
heartbeat:
  daily: true
confirmation:
  required_when:
    - creating_accounting_question
```

```python
# apps/api/app/skills/python_finance/analytics/anomalies.py
from __future__ import annotations

import pandas as pd


def detect_amount_anomalies(
    records: list[dict],
    amount_col: str = "amount",
    group_col: str = "category",
    z_threshold: float = 2.5,
) -> dict:
    df = pd.DataFrame(records)
    if df.empty:
        return {"anomalies": [], "warnings": ["No records."]}

    if group_col not in df.columns:
        df[group_col] = "all"

    df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0.0).abs()

    def add_z_score(group: pd.DataFrame) -> pd.DataFrame:
        mean = group[amount_col].mean()
        std = group[amount_col].std()
        group = group.copy()
        group["z_score"] = 0.0 if not std or pd.isna(std) else (group[amount_col] - mean) / std
        return group

    scored = df.groupby(group_col, group_keys=False).apply(add_z_score)
    anomalies = scored[scored["z_score"].abs() >= z_threshold]

    questions = [
        {
            "record_id": row.get("id"),
            "question": f"Is this {row.get(group_col)} amount expected?",
            "reason": "Amount is unusual compared with similar records.",
        }
        for _, row in anomalies.iterrows()
    ]

    return {
        "anomalies": anomalies.to_dict("records"),
        "questions": questions,
    }
```

---

# 18. Skill: `chart_data_generator`

```yaml
name: chart_data_generator
pack: python_finance
mode: both
risk_level: low
description: Converts report and analytics outputs into dashboard-ready chart JSON.
heartbeat:
  weekly: true
memory:
  reads:
    - dashboard_metric_preference
  writes:
    - dashboard_chart_observation
confirmation:
  required_when:
    - activating_dashboard_widget
```

```python
# apps/api/app/skills/python_finance/visualization/chart_data.py
from __future__ import annotations


def line_chart(title: str, rows: list[dict], x: str, y: str) -> dict:
    return {"type": "line", "title": title, "xKey": x, "yKey": y, "data": rows}


def bar_chart(title: str, rows: list[dict], x: str, y: str) -> dict:
    return {"type": "bar", "title": title, "xKey": x, "yKey": y, "data": rows}


def pie_chart(title: str, rows: list[dict], label: str, value: str) -> dict:
    return {"type": "pie", "title": title, "labelKey": label, "valueKey": value, "data": rows}


def multi_line_chart(title: str, rows: list[dict], x: str, series: list[str]) -> dict:
    return {"type": "multi_line", "title": title, "xKey": x, "series": series, "data": rows}
```

---

# 19. Agent Routing Rules

```yaml
routing:
  user_asks_cashflow:
    call:
      - financial_time_series_analyzer
      - rolling_statistics_calculator
      - chart_data_generator
  user_asks_portfolio_risk:
    call:
      - returns_calculator
      - portfolio_allocation_analyzer
      - risk_metrics_calculator
  user_asks_dashboard:
    call:
      - chart_data_generator
      - dashboard_widget_generator
  user_asks_goal_probability:
    call:
      - monte_carlo_goal_simulator
```

---

# 20. Heartbeat Plan

```yaml
daily:
  - finance_dataframe_profiler
  - anomaly_detector

weekly:
  - financial_time_series_analyzer
  - rolling_statistics_calculator
  - chart_data_generator

monthly:
  - returns_calculator
  - risk_metrics_calculator
  - portfolio_allocation_analyzer
  - monte_carlo_goal_simulator
```

---

# 21. Tests

```txt
test_clean_financial_records
test_profile_records
test_analyze_time_series_monthly
test_calculate_returns
test_rolling_statistics
test_risk_metrics
test_portfolio_allocation
test_monte_carlo_goal
test_anomaly_detection
test_chart_generation
test_registry_exposes_all_skills
test_skill_audit_created
test_no_broker_execution_available
```

---

# 22. Acceptance Criteria

```txt
- Agent calls deterministic Python functions for analytics.
- Dashboard widgets use Python outputs.
- Reports use Python outputs.
- Heartbeat uses Python finance skills.
- Memory stores preferences, thresholds, snapshots, and observations.
- Portfolio analysis remains educational.
- No trading execution exists.
- No user-provided code is executed.
- Tests pass.
```
