# Integration Review Report: Skill Packs + Agent Enhancement

**Date:** 2026-05-06  
**Scope:** Python Finance, Accounting, and Personal Finance skill packs; OpenAI provider; SkillPlanner; ConfirmationEngine audit

---

## Summary

Three built-in skill packs have been integrated into the MIAF agent. All 21 skill manifests are mirrored to `apps/api/skills/` (the container bind-mount path). The agent now has 37 registered tools, a cross-skill intent planner, and a full OpenAI provider implementation.

---

## What was implemented

### 1. Skill pack functions (`apps/api/app/skills/`)

| Pack | Modules | Key capabilities |
|---|---|---|
| `python_finance` | `core/`, `analytics/`, `visualization/` | Dataframe utilities, time-series resampling (`ME` frequency), Monte Carlo (`seed=42`), VaR/CVaR, portfolio allocation, anomaly detection (z-score), chart data generation |
| `accounting` | `core/`, `ledger/`, `reporting/`, `workflows/` | Journal validator (Decimal arithmetic, debit/credit exclusivity), trial balance, income statement, balance sheet (assets == liabilities + equity), AR/AP aging, depreciation (straight-line), bank reconciliation, accounting questions |
| `personal_finance` | `calculations/`, `behavior/`, `meetings/` | Budget variance, cashflow (savings rate), emergency fund plan, debt payoff (avalanche), room-for-error score (100-point), spending habits, lifestyle creep detection, subscription analysis, weekly money meeting agenda |

### 2. OpenAI provider (`app/services/agent.py`)

- Full `OpenAIProvider` class using `openai>=1.0.0` SDK
- `_tool_to_openai_schema()` converts `Tool` → OpenAI function schema (`{"type":"function","function":{...}}`)
- Falls back to `HeuristicProvider` when SDK or key unavailable
- Parses `tool_calls` from `response.choices[0].message.tool_calls`

### 3. SkillPlanner (`app/services/agent.py`)

- `SkillPlanner.INTENT_PLANS` maps 24 intent keywords to ordered tool lists
- `suggest(message) -> list[str]` returns de-duplicated ordered suggestions
- Injected as hint into LLM system prompt (all three providers: Anthropic, OpenAI, Heuristic)
- **Does not auto-execute tools** — the LLM decides

### 4. New agent tools (11 skill-backed, read-only)

| Tool name | Skill function |
|---|---|
| `generate_income_statement_data` | `accounting.ledger.financial_statements.generate_income_statement` |
| `generate_balance_sheet_data` | `accounting.ledger.financial_statements.generate_balance_sheet` |
| `generate_trial_balance_data` | `accounting.ledger.trial_balance.generate_trial_balance` |
| `analyze_personal_cashflow` | `personal_finance.calculations.cashflow.calculate_personal_cashflow` |
| `analyze_budget_variance` | `personal_finance.calculations.budget.budget_variance` |
| `check_room_for_error` | `personal_finance.calculations.room_for_error.calculate_room_for_error_score` |
| `analyze_portfolio_risk` | `python_finance.analytics.risk.calculate_risk_metrics` |
| `detect_financial_anomalies` | `python_finance.analytics.anomalies.detect_amount_anomalies` |
| `generate_chart_data` | `python_finance.visualization.chart_data.generate_chart` |
| `build_money_meeting_agenda` | `personal_finance.meetings.weekly_money_meeting.build_weekly_money_meeting_agenda` |
| `create_accounting_question` | `accounting.workflows.questions.generate_accounting_question` |

All 11 are read-only; none require confirmation.

### 5. ConfirmationEngine audit

`ConfirmationEngine._sensitive` now contains:
- `post_journal_entry` ✓
- `create_invoice` ✓ (added — creates financial obligations)
- `record_invoice_payment` ✓
- `record_bill_payment` ✓

Pure analytics tools (`generate_income_statement_data`, `check_room_for_error`, etc.) are intentionally **not** in the sensitive set.

### 6. Memory suggestions

`check_room_for_error` and `detect_financial_anomalies` include a `memory_suggestion` field when risk level is medium/high or anomalies are found. The agent service surfaces these to the caller; they are not auto-saved.

### 7. Heartbeat skill integration

Heartbeat runs call skill pack functions inside `try/except Exception` blocks so a broken or missing skill never fails a heartbeat run. Current integrations:
- `room_for_error` score appended to personal check summaries
- Anomaly detection appended to business check summaries
- Emergency fund plan appended to monthly personal close
- Weekly money meeting agenda appended to weekly personal report
- Income statement stub appended to weekly business report

---

## Test coverage

| Test file | Count | Coverage |
|---|---|---|
| `test_skill_packs.py` | 77 tests | All three packs, all public functions |
| `test_agent_tools.py` | 5 tests | OpenAI fallback, tool schema format, SkillPlanner, memory_suggestion, heartbeat resilience |
| Pre-existing agent/heartbeat/skill tests | ~105 tests | Unchanged pass rate |

---

## Known limitations

- `openai` SDK requires Docker image rebuild (`docker compose build api`) when first adding the dependency.
- `GeminiProvider` is a stub (delegates to `HeuristicProvider`). Full Gemini implementation is a future phase.
- Skill packs do not yet have a UI surface beyond `/skills` toggle listing. Chart data output (`generate_chart_data`) is not yet rendered in the web app.
- Export auditing and per-IP cross-endpoint rate limits are still outstanding from Phase 12.

---

## Invariants verified

- ✅ All skill handler functions are pure (no DB, no secrets, no shell)
- ✅ Lazy imports used in all agent tool handlers
- ✅ Heartbeat skill calls wrapped in `try/except Exception`
- ✅ Investment tools carry risk disclaimer
- ✅ No tool invents numbers — all figures come from deterministic functions
- ✅ `create_invoice` gated behind confirmation
- ✅ Analytics tools are NOT confirmation-gated
