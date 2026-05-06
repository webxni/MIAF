# MIAF Skill Pack: Personal Finance  
## File: `personal_finance.md`


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

**Book:** `The-Psychology-of-Money-Morgan-Housel.pdf`  
**Primary use inside MIAF:** personal finance behavior, spending discipline, saving, room for error, risk behavior, enough, financial freedom, patience, and money meetings.

## Why This Skill Pack Exists

Personal finance is not only math. It is behavior.

MIAF must help the user:

- save consistently
- spend intentionally
- manage debt calmly
- build an emergency fund
- avoid lifestyle creep
- keep room for error
- define “enough”
- understand risk
- avoid impulsive investment behavior
- review money decisions regularly
- connect personal money to business owner decisions

The agent should not shame the user.  
It should be calm, practical, and consistent.

---

# 1. Skill Pack Manifest

```yaml
skill_pack:
  id: personal_finance
  version: 1.1.0
  source_book: The Psychology of Money
  mode: personal
  purpose: >
    Provides behavioral finance coaching, personal budgeting, savings,
    debt planning, money meetings, and daily financial heartbeat.
  primary_runtime: python
  requires_llm: true
  deterministic_calculations_required: true
  agent_can_call: true
  heartbeat_can_call: true
  dashboard_can_call: true
  memory_enabled: true
  audit_required: true
  approval_required_for:
    - budget_target_change
    - savings_goal_change
    - debt_strategy_change
    - investment_policy_change
    - recurring_money_meeting
```

---

# 2. Directory Structure

```txt
apps/api/app/skills/personal_finance/
  __init__.py
  manifest.yaml
  registry.py
  schemas.py
  memory.py
  audit.py
  service.py

  calculations/
    cashflow.py
    budget.py
    emergency_fund.py
    debt.py
    savings.py
    net_worth.py
    freedom.py
    room_for_error.py

  behavior/
    habits.py
    spending_triggers.py
    lifestyle_creep.py
    subscriptions.py
    enough.py
    impulse_guardrails.py
    money_journal.py

  meetings/
    weekly_money_meeting.py
    budget_review.py
    decision_log.py

  reports/
    personal_report.py
    behavior_report.py
    goal_report.py

  tests/
```

---

# 3. Unified Personal Finance Skill Format

```yaml
name: budget_coach
version: 1.0.0
pack: personal_finance
mode: personal
risk_level: medium
description: Helps user maintain realistic budget and improve money behavior.
inputs:
  schema: BudgetCoachInput
outputs:
  schema: BudgetCoachOutput
memory:
  reads:
    - budget_style
    - financial_goals
    - spending_triggers
  writes:
    - budget_observation
    - accepted_suggestion
heartbeat:
  daily: true
  weekly: true
  monthly: true
confirmation:
  required_when:
    - changing_budget_target
audit:
  events:
    - personal_finance.skill.started
    - personal_finance.skill.completed
```

---

# 4. Memory Schema

```yaml
memory_types:
  personal_finance_profile:
    fields:
      - income_frequency
      - monthly_income_estimate
      - monthly_expense_estimate
      - household_context
      - business_dependency
  financial_goal:
    fields:
      - name
      - target_amount
      - target_date
      - priority
      - emotional_reason
  budget_style:
    fields:
      - method
      - strictness
      - preferred_review_frequency
  spending_trigger:
    fields:
      - category
      - merchant
      - emotion_or_context
      - user_note
  savings_preference:
    fields:
      - preferred_savings_method
      - automatic_transfer_preference
      - target_savings_rate
  debt_strategy:
    fields:
      - strategy
      - reason
      - approved
  definition_of_enough:
    fields:
      - monthly_lifestyle_target
      - freedom_goal
      - non_negotiables
      - avoid_list
  room_for_error_policy:
    fields:
      - emergency_months_target
      - cash_buffer_target
      - max_debt_pressure
      - tax_buffer_required
  behavioral_observation:
    fields:
      - observation
      - evidence
      - user_confirmed
  money_meeting_preference:
    fields:
      - frequency
      - agenda_style
      - preferred_day
      - preferred_tone
```

## Memory Write Policy

```yaml
automatic_allowed:
  - spending_pattern_observation
  - subscription_candidate
  - habit_observation
  - daily_heartbeat_note

approval_required:
  - financial_goal
  - budget_style
  - savings_preference
  - debt_strategy
  - definition_of_enough
  - room_for_error_policy
  - recurring_money_meeting
```

---

# 5. Core Python Script: Personal Finance Schemas

```python
# apps/api/app/skills/personal_finance/schemas.py
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class PersonalFinanceWarning(BaseModel):
    code: str
    message: str
    severity: str = "info"


class PersonalFinanceResult(BaseModel):
    skill_name: str
    success: bool
    data: dict = Field(default_factory=dict)
    questions: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    warnings: List[PersonalFinanceWarning] = Field(default_factory=list)
    memory_writes: List[dict] = Field(default_factory=list)
    requires_review: bool = False
```

---

# 6. Skill: `personal_finance_profile_builder`

```yaml
name: personal_finance_profile_builder
pack: personal_finance
mode: personal
risk_level: medium
description: Creates the user's personal finance operating profile and first priorities.
memory:
  writes:
    - personal_finance_profile
    - financial_goal
heartbeat:
  monthly: true
confirmation:
  required_when:
    - saving_profile
```

```python
# apps/api/app/skills/personal_finance/calculations/profile.py
from __future__ import annotations


def build_personal_finance_priorities(profile: dict) -> dict:
    priorities = []

    if profile.get("monthly_cashflow", 0) < 0:
        priorities.append("stop_negative_cashflow")

    if profile.get("has_high_interest_debt"):
        priorities.append("stabilize_high_interest_debt")

    if profile.get("emergency_fund_months", 0) < 1:
        priorities.append("build_starter_emergency_fund")

    if profile.get("emergency_fund_months", 0) < profile.get("target_emergency_months", 6):
        priorities.append("build_full_emergency_fund")

    if profile.get("savings_rate", 0) < profile.get("target_savings_rate", 0.15):
        priorities.append("increase_savings_rate")

    priorities.append("review_long_term_goals")

    return {
        "priorities": priorities,
        "first_30_day_plan": priorities[:3],
    }
```

---

# 7. Skill: `cashflow_and_savings_rate`

```yaml
name: cashflow_and_savings_rate
pack: personal_finance
mode: personal
risk_level: low
description: Calculates personal income, expenses, cashflow, and savings rate.
heartbeat:
  daily: true
  weekly: true
memory:
  writes:
    - savings_rate_observation
```

```python
# apps/api/app/skills/personal_finance/calculations/cashflow.py
from __future__ import annotations

import pandas as pd


def calculate_personal_cashflow(transactions: list[dict]) -> dict:
    df = pd.DataFrame(transactions)
    if df.empty:
        return {
            "income": 0.0,
            "expenses": 0.0,
            "net_cashflow": 0.0,
            "savings_rate": 0.0,
            "warnings": ["No transactions available."],
        }

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    income = float(df[df["type"] == "income"]["amount"].sum())
    expenses = float(df[df["type"] == "expense"]["amount"].abs().sum())
    net_cashflow = income - expenses
    savings_rate = net_cashflow / income if income > 0 else 0.0

    return {
        "income": income,
        "expenses": expenses,
        "net_cashflow": net_cashflow,
        "savings_rate": savings_rate,
    }
```

---

# 8. Skill: `budget_coach`

```yaml
name: budget_coach
pack: personal_finance
mode: personal
risk_level: medium
description: Helps user create and adjust a realistic budget.
memory:
  reads:
    - budget_style
    - financial_goal
  writes:
    - budget_observation
heartbeat:
  daily: true
  weekly: true
  monthly: true
confirmation:
  required_when:
    - changing_budget_target
```

```python
# apps/api/app/skills/personal_finance/calculations/budget.py
from __future__ import annotations


def calculate_budget_summary(income: float, budget_lines: list[dict]) -> dict:
    total_budgeted = sum(float(line.get("amount", 0)) for line in budget_lines)
    remaining = income - total_budgeted

    by_type = {}
    for line in budget_lines:
        kind = line.get("type", "uncategorized")
        by_type[kind] = by_type.get(kind, 0.0) + float(line.get("amount", 0))

    return {
        "income": income,
        "total_budgeted": total_budgeted,
        "remaining": remaining,
        "by_type": by_type,
        "balanced": abs(remaining) < 0.01,
        "warnings": ["Budget exceeds income."] if remaining < 0 else [],
    }


def budget_variance(budget_lines: list[dict], actual_by_category: dict[str, float]) -> dict:
    rows = []
    for line in budget_lines:
        category = line["category"]
        budgeted = float(line.get("amount", 0))
        actual = float(actual_by_category.get(category, 0))
        remaining = budgeted - actual
        rows.append({
            "category": category,
            "budgeted": budgeted,
            "actual": actual,
            "remaining": remaining,
            "percent_used": actual / budgeted if budgeted else 0.0,
            "status": "overspent" if remaining < 0 else "ok",
        })
    return {"rows": rows, "overspent": [r for r in rows if r["status"] == "overspent"]}
```

---

# 9. Skill: `emergency_fund_planner`

```yaml
name: emergency_fund_planner
pack: personal_finance
mode: personal
risk_level: medium
description: Calculates emergency fund target, gap, months covered, and contribution plan.
memory:
  reads:
    - room_for_error_policy
    - financial_goal
  writes:
    - emergency_fund_observation
heartbeat:
  weekly: true
confirmation:
  required_when:
    - changing_emergency_fund_target
```

```python
# apps/api/app/skills/personal_finance/calculations/emergency_fund.py
from __future__ import annotations


def emergency_fund_plan(
    monthly_essential_expenses: float,
    current_fund: float,
    target_months: int = 6,
    monthly_contribution: float = 0.0,
) -> dict:
    target = monthly_essential_expenses * target_months
    gap = max(target - current_fund, 0.0)
    months_covered = current_fund / monthly_essential_expenses if monthly_essential_expenses else 0.0
    months_to_goal = gap / monthly_contribution if monthly_contribution > 0 else None

    return {
        "target": target,
        "current_fund": current_fund,
        "gap": gap,
        "months_covered": months_covered,
        "monthly_contribution": monthly_contribution,
        "months_to_goal": months_to_goal,
    }
```

---

# 10. Skill: `room_for_error_checker`

```yaml
name: room_for_error_checker
pack: personal_finance
mode: personal
risk_level: medium
description: Scores whether the user has enough margin of safety.
memory:
  reads:
    - room_for_error_policy
    - personal_finance_profile
  writes:
    - room_for_error_observation
heartbeat:
  daily: true
confirmation:
  required_when:
    - changing_room_for_error_policy
```

```python
# apps/api/app/skills/personal_finance/calculations/room_for_error.py
from __future__ import annotations


def calculate_room_for_error_score(profile: dict) -> dict:
    score = 100
    issues = []

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
```

---

# 11. Skill: `debt_payoff_planner`

```yaml
name: debt_payoff_planner
pack: personal_finance
mode: personal
risk_level: medium
description: Ranks debt payoff strategy based on motivation, interest, or cashflow pressure.
memory:
  reads:
    - debt_strategy
  writes:
    - debt_plan_observation
heartbeat:
  monthly: true
confirmation:
  required_when:
    - changing_debt_strategy
```

```python
# apps/api/app/skills/personal_finance/calculations/debt.py
from __future__ import annotations


def choose_debt_strategy(user_preference: str, debts: list[dict]) -> dict:
    if user_preference == "motivation":
        strategy = "snowball"
        key = lambda d: float(d.get("balance", 0))
    elif user_preference == "interest":
        strategy = "avalanche"
        key = lambda d: -float(d.get("interest_rate", 0))
    else:
        strategy = "cashflow_relief"
        key = lambda d: -float(d.get("minimum_payment", 0))

    ordered = sorted(debts, key=key)
    return {
        "strategy": strategy,
        "ordered_debts": [
            {**debt, "priority": index + 1}
            for index, debt in enumerate(ordered)
        ],
    }
```

---

# 12. Skill: `spending_habit_analyzer`

```yaml
name: spending_habit_analyzer
pack: personal_finance
mode: personal
risk_level: low
description: Finds spending patterns without shaming the user.
memory:
  reads:
    - spending_trigger
  writes:
    - spending_pattern_observation
heartbeat:
  daily: true
```

```python
# apps/api/app/skills/personal_finance/behavior/habits.py
from __future__ import annotations

import pandas as pd


def analyze_spending_habits(transactions: list[dict]) -> dict:
    df = pd.DataFrame(transactions)
    if df.empty:
        return {"patterns": [], "questions": []}

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0).abs()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["day_of_week"] = df["date"].dt.day_name()

    top_merchants = []
    if "merchant" in df.columns:
        top_merchants = (
            df.groupby("merchant")["amount"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
            .to_dict("records")
        )

    top_categories = []
    if "category" in df.columns:
        top_categories = (
            df.groupby("category")["amount"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
            .to_dict("records")
        )

    questions = []
    if top_merchants:
        merchant = top_merchants[0]["merchant"]
        questions.append(f"Do you want me to watch spending at {merchant} more closely?")

    return {
        "top_merchants": top_merchants,
        "top_categories": top_categories,
        "questions": questions,
    }
```

---

# 13. Skill: `subscription_review_assistant`

```yaml
name: subscription_review_assistant
pack: personal_finance
mode: personal
risk_level: low
description: Detects recurring subscription-like expenses.
memory:
  reads:
    - subscription_preference
  writes:
    - subscription_candidate
heartbeat:
  weekly: true
confirmation:
  required_when:
    - creating_cancel_task
```

```python
# apps/api/app/skills/personal_finance/behavior/subscriptions.py
from __future__ import annotations

import pandas as pd


def identify_subscription_candidates(transactions: list[dict]) -> dict:
    df = pd.DataFrame(transactions)
    if df.empty or "merchant" not in df.columns:
        return {"subscriptions": []}

    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0).abs()

    candidates = []
    for merchant, group in df.groupby("merchant"):
        if len(group) >= 3:
            amount_std = group["amount"].std()
            avg_amount = group["amount"].mean()
            if avg_amount and (pd.isna(amount_std) or amount_std / avg_amount < 0.10):
                candidates.append({
                    "merchant": merchant,
                    "average_amount": float(avg_amount),
                    "occurrences": int(len(group)),
                    "question": f"Do you still use {merchant} enough to keep paying for it?",
                })

    return {"subscriptions": candidates}
```

---

# 14. Skill: `lifestyle_creep_detector`

```yaml
name: lifestyle_creep_detector
pack: personal_finance
mode: personal
risk_level: low
description: Detects when expenses grow faster than income.
memory:
  writes:
    - lifestyle_creep_observation
heartbeat:
  monthly: true
```

```python
# apps/api/app/skills/personal_finance/behavior/lifestyle_creep.py
from __future__ import annotations

import pandas as pd


def detect_lifestyle_creep(monthly: list[dict]) -> dict:
    df = pd.DataFrame(monthly)
    if len(df) < 3:
        return {"detected": False, "warnings": ["Need at least 3 months."]}

    income_growth = df["income"].iloc[-1] / df["income"].iloc[0] - 1 if df["income"].iloc[0] else 0
    expense_growth = df["expenses"].iloc[-1] / df["expenses"].iloc[0] - 1 if df["expenses"].iloc[0] else 0
    savings_rate_change = df["savings_rate"].iloc[-1] - df["savings_rate"].iloc[0]

    detected = expense_growth > income_growth and savings_rate_change <= 0
    return {
        "detected": bool(detected),
        "income_growth": float(income_growth),
        "expense_growth": float(expense_growth),
        "savings_rate_change": float(savings_rate_change),
    }
```

---

# 15. Skill: `enough_guardrail`

```yaml
name: enough_guardrail
pack: personal_finance
mode: personal
risk_level: medium
description: Helps user define enough and avoid chasing spending that does not improve life.
memory:
  reads:
    - definition_of_enough
  writes:
    - definition_of_enough_candidate
heartbeat:
  monthly: true
confirmation:
  required_when:
    - saving_definition_of_enough
```

## Behavior

The agent should ask:

```txt
What does money need to do for you right now?
What expenses actually improve your life?
What spending creates stress later?
What is the minimum monthly freedom number?
What is enough income for your current season?
```

This skill is mostly conversational but must use deterministic numbers from:

```txt
cashflow_and_savings_rate
room_for_error_checker
financial_freedom_tracker
```

---

# 16. Skill: `investment_behavior_guardrail`

```yaml
name: investment_behavior_guardrail
pack: personal_finance
mode: personal
risk_level: high
description: Prevents impulsive investment behavior and protects emergency money.
memory:
  reads:
    - risk_tolerance
    - financial_goal
    - room_for_error_policy
  writes:
    - investment_behavior_observation
heartbeat:
  monthly: true
confirmation:
  required_when:
    - saving_investment_policy
```

## Triggers

```txt
hot stock question
panic selling language
FOMO language
using emergency fund to invest
high-interest debt plus risky investment
large speculative allocation
```

## Safety

```yaml
forbidden:
  - execute_trade
  - recommend_specific_trade_as_instruction
  - guarantee_return
allowed:
  - explain_risk
  - ask_time_horizon
  - check_emergency_fund
  - suggest_waiting_period
  - suggest_professional_advice
```

---

# 17. Skill: `weekly_money_meeting_assistant`

```yaml
name: weekly_money_meeting_assistant
pack: personal_finance
mode: personal
risk_level: low
description: Creates a review agenda and logs decisions.
memory:
  reads:
    - money_meeting_preference
    - financial_goal
  writes:
    - money_meeting_note
    - decision_log
heartbeat:
  weekly: true
confirmation:
  required_when:
    - scheduling_recurring_meeting
```

```python
# apps/api/app/skills/personal_finance/meetings/weekly_money_meeting.py
from __future__ import annotations


def build_weekly_money_meeting_agenda(context: dict) -> dict:
    agenda = [
        "Review income and expenses",
        "Review transactions needing classification",
        "Review budget progress",
        "Review savings and emergency fund",
        "Review upcoming bills",
        "Choose one improvement for next week",
    ]

    if context.get("has_business"):
        agenda.insert(2, "Review business cashflow and owner draws")

    if context.get("has_debt"):
        agenda.append("Review debt payoff progress")

    if context.get("has_open_questions"):
        agenda.insert(0, "Resolve open accounting questions")

    return {"agenda": agenda}
```

---

# 18. Skill: `daily_money_heartbeat`

```yaml
name: daily_money_heartbeat
pack: personal_finance
mode: personal
risk_level: low
description: Creates calm, useful daily financial check-ins.
heartbeat:
  daily: true
memory:
  reads:
    - financial_goal
    - budget_style
    - room_for_error_policy
  writes:
    - daily_heartbeat_note
confirmation:
  required: false
```

## Daily Heartbeat Rules

```yaml
do:
  - group_questions
  - show_only_important_items
  - give_one_next_action
  - be calm
  - avoid shame
do_not:
  - spam
  - lecture
  - exaggerate
  - create anxiety
  - change records without approval
```

---

# 19. Skill: `personal_finance_reporter`

```yaml
name: personal_finance_reporter
pack: personal_finance
mode: personal
risk_level: low
description: Generates personal finance report data and review questions.
heartbeat:
  weekly: true
  monthly: true
memory:
  reads:
    - reporting_preference
    - financial_goal
  writes:
    - personal_report_snapshot
```

## Reports

```txt
monthly cashflow
budget vs actual
savings rate
emergency fund progress
debt progress
subscription review
spending habit report
financial freedom report
room for error report
personal/business dependency report
```

---

# 20. Heartbeat Plan

```yaml
daily:
  - daily_money_heartbeat
  - cashflow_and_savings_rate
  - budget_coach
  - spending_habit_analyzer
  - room_for_error_checker

weekly:
  - weekly_money_meeting_assistant
  - subscription_review_assistant
  - personal_finance_reporter
  - savings_rate_coach

monthly:
  - emergency_fund_planner
  - debt_payoff_planner
  - lifestyle_creep_detector
  - enough_guardrail
  - investment_behavior_guardrail
```

---

# 21. Agent Routing Rules

```yaml
routing:
  user_asks_how_am_i_doing:
    call:
      - cashflow_and_savings_rate
      - room_for_error_checker
      - emergency_fund_planner
      - personal_finance_reporter

  user_asks_spend_less:
    call:
      - spending_habit_analyzer
      - subscription_review_assistant
      - budget_coach

  user_asks_afford_purchase:
    call:
      - budget_coach
      - emergency_fund_planner
      - room_for_error_checker

  user_asks_investment_question:
    call:
      - investment_behavior_guardrail
      - risk_tolerance_profile
```

---

# 22. Dashboard Widgets

```txt
Savings Rate
Emergency Fund Months
Budget vs Actual
Top Spending Categories
Subscription Candidates
Debt Payoff Progress
Financial Freedom Months
Room for Error Score
Lifestyle Creep Warning
Weekly Money Meeting Agenda
Personal/Business Dependency
```

---

# 23. Tests

```txt
test_profile_priorities
test_cashflow_savings_rate
test_budget_summary
test_budget_variance
test_emergency_fund_plan
test_room_for_error_score
test_debt_strategy_motivation
test_debt_strategy_interest
test_spending_habit_analyzer
test_subscription_candidates
test_lifestyle_creep
test_weekly_money_meeting_agenda
test_daily_heartbeat_groups_questions
test_investment_guardrail_blocks_trading
```

---

# 24. Acceptance Criteria

```txt
- MIAF can coach without shaming.
- MIAF calculates savings rate and cashflow deterministically.
- MIAF tracks emergency fund and room for error.
- MIAF detects subscriptions and lifestyle creep.
- MIAF creates weekly money meeting agendas.
- MIAF stores goals, habits, preferences, and decisions in memory.
- Heartbeat gives useful daily/weekly/monthly check-ins.
- Agent suggestions improve from accepted/rejected feedback.
- No trading or money movement exists.
```
