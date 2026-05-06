# MIAF Skill Pack: Accounting  
## File: `accounting.md`


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

**Book:** `Principles-of-Financial-Accounting.pdf`  
**Primary use inside MIAF:** double-entry accounting, accounting cycle, journal entries, ledgers, trial balance, statements, accruals, adjustments, AR/AP, bank reconciliation, depreciation, inventory, and closing.

## Why This Skill Pack Exists

MIAF must be **accounting-first**.

The agent can classify, explain, and ask questions, but the accounting engine must enforce the rules:

- journal entries must balance
- trial balance must balance
- financial statements must derive from posted ledger data
- posted entries must not be silently edited
- corrections must be reversals or adjustments
- uncertain entries must become questions or drafts

---

# 1. Skill Pack Manifest

```yaml
skill_pack:
  id: accounting
  version: 1.1.0
  source_book: Principles of Financial Accounting
  mode: business
  purpose: >
    Provides deterministic double-entry accounting, financial statements,
    posting validation, questions, close workflow, and bookkeeping controls.
  primary_runtime: python
  requires_llm: false
  agent_can_call: true
  heartbeat_can_call: true
  dashboard_can_call: true
  memory_enabled: true
  audit_required: true
  approval_required_for:
    - posting_journal_entry
    - voiding_journal_entry
    - adjusting_entry
    - closing_period
    - owner_draw_policy
    - tax_sensitive_classification
    - broad_accounting_rule
```

---

# 2. Directory Structure

```txt
apps/api/app/skills/accounting/
  __init__.py
  manifest.yaml
  registry.py
  schemas.py
  memory.py
  audit.py
  service.py

  core/
    accounts.py
    normal_balances.py
    money.py
    posting.py
    validators.py

  ledger/
    journal.py
    general_ledger.py
    trial_balance.py
    financial_statements.py
    close.py

  workflows/
    ar.py
    ap.py
    bank_reconciliation.py
    adjusting_entries.py
    depreciation.py
    inventory.py
    owner_equity.py
    questions.py
    policy_learning.py

  tests/
```

---

# 3. Unified Accounting Skill Format

```yaml
name: journal_entry_validator
version: 1.0.0
pack: accounting
mode: business
risk_level: high
description: Validates that a journal entry is structurally correct and balanced.
inputs:
  schema: JournalEntry
outputs:
  schema: JournalValidationResult
memory:
  reads:
    - accounting_policy
    - account_mapping_rule
  writes:
    - validation_failure_observation
heartbeat:
  daily: true
confirmation:
  required: false
audit:
  events:
    - accounting.validation.started
    - accounting.validation.completed
tests:
  - test_balanced_entry_valid
  - test_unbalanced_entry_rejected
```

---

# 4. Memory Schema

```yaml
memory_types:
  accounting_policy:
    description: User-approved accounting policy for the entity.
    fields:
      - entity_id
      - policy_name
      - policy_value
      - effective_date
      - approved_by
  account_mapping_rule:
    description: Approved rule mapping vendor/customer/merchant to account.
    fields:
      - entity_id
      - counterparty
      - account_id
      - conditions
      - confidence
      - approved
  vendor_accounting_rule:
    description: Vendor-specific accounting treatment.
    fields:
      - vendor
      - default_debit_account
      - default_credit_account
      - tax_sensitive
      - review_required
  customer_revenue_rule:
    description: Customer-specific revenue account mapping.
    fields:
      - customer
      - revenue_account
      - payment_terms
  owner_draw_policy:
    description: Rules for business-to-personal transfers.
    fields:
      - default_classification
      - approval_threshold
      - tax_reserve_check_required
  close_preference:
    description: Monthly close requirements.
    fields:
      - required_checks
      - review_frequency
      - reporting_package
  unresolved_accounting_pattern:
    description: Repeated unresolved or low-confidence pattern.
    fields:
      - pattern
      - examples
      - suggested_question
```

## Memory Rules

```yaml
memory_write_policy:
  automatic_allowed:
    - validation_failure_observation
    - unresolved_accounting_pattern
  approval_required:
    - accounting_policy
    - account_mapping_rule
    - vendor_accounting_rule
    - customer_revenue_rule
    - owner_draw_policy
```

---

# 5. Core Python Script: Schemas

```python
# apps/api/app/skills/accounting/schemas.py
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class AccountType(str, Enum):
    asset = "asset"
    liability = "liability"
    equity = "equity"
    income = "income"
    expense = "expense"
    contra_asset = "contra_asset"
    contra_liability = "contra_liability"
    contra_equity = "contra_equity"
    contra_income = "contra_income"
    contra_expense = "contra_expense"


class NormalSide(str, Enum):
    debit = "debit"
    credit = "credit"


class Account(BaseModel):
    id: str
    code: str
    name: str
    type: AccountType
    normal_side: NormalSide
    parent_id: Optional[str] = None
    active: bool = True


class JournalLine(BaseModel):
    account_id: str
    debit: float = 0.0
    credit: float = 0.0
    memo: Optional[str] = None


class JournalEntry(BaseModel):
    id: Optional[str] = None
    entity_id: str
    date: str
    description: str
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    status: str = "draft"
    lines: List[JournalLine] = Field(default_factory=list)


class JournalValidationResult(BaseModel):
    valid: bool
    total_debits: float
    total_credits: float
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
```

---

# 6. Core Python Script: Normal Balances

```python
# apps/api/app/skills/accounting/core/normal_balances.py
from __future__ import annotations

NORMAL_BALANCE = {
    "asset": "debit",
    "expense": "debit",
    "contra_liability": "debit",
    "contra_equity": "debit",
    "contra_income": "debit",
    "liability": "credit",
    "equity": "credit",
    "income": "credit",
    "contra_asset": "credit",
    "contra_expense": "credit",
}


def account_effect(account_type: str, debit: float, credit: float) -> str:
    normal = NORMAL_BALANCE[account_type]
    if debit > 0:
        return "increase" if normal == "debit" else "decrease"
    if credit > 0:
        return "increase" if normal == "credit" else "decrease"
    return "no_effect"


def signed_balance(account_type: str, debit: float, credit: float) -> float:
    normal = NORMAL_BALANCE[account_type]
    return debit - credit if normal == "debit" else credit - debit
```

---

# 7. Skill: `journal_entry_validator`

```yaml
name: journal_entry_validator
pack: accounting
mode: business
risk_level: high
description: Validates journal entry structure, debit/credit exclusivity, and balance.
heartbeat:
  daily: true
memory:
  writes:
    - validation_failure_observation
confirmation:
  required: false
```

```python
# apps/api/app/skills/accounting/core/validators.py
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def money(value: float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_journal_entry(entry: dict) -> dict:
    lines = entry.get("lines", [])
    errors = []
    warnings = []

    if len(lines) < 2:
        errors.append("A journal entry must have at least two lines.")

    total_debits = Decimal("0.00")
    total_credits = Decimal("0.00")

    for index, line in enumerate(lines):
        debit = money(line.get("debit", 0))
        credit = money(line.get("credit", 0))

        total_debits += debit
        total_credits += credit

        if not line.get("account_id"):
            errors.append(f"Line {index + 1} is missing account_id.")
        if debit < 0 or credit < 0:
            errors.append(f"Line {index + 1} cannot have negative debit or credit.")
        if debit > 0 and credit > 0:
            errors.append(f"Line {index + 1} cannot have both debit and credit.")
        if debit == 0 and credit == 0:
            errors.append(f"Line {index + 1} must have debit or credit.")

    if total_debits != total_credits:
        errors.append(
            f"Entry is not balanced. Debits {total_debits} do not equal credits {total_credits}."
        )

    return {
        "valid": not errors,
        "total_debits": float(total_debits),
        "total_credits": float(total_credits),
        "errors": errors,
        "warnings": warnings,
    }
```

---

# 8. Skill: `journal_entry_builder`

```yaml
name: journal_entry_builder
pack: accounting
mode: business
risk_level: high
description: Builds journal entry drafts using approved accounting templates.
memory:
  reads:
    - vendor_accounting_rule
    - customer_revenue_rule
    - owner_draw_policy
  writes:
    - draft_entry_created
confirmation:
  required_when:
    - posting
    - new_account_mapping
    - owner_draw
    - tax_sensitive
```

```python
# apps/api/app/skills/accounting/ledger/journal.py
from __future__ import annotations


def build_simple_journal_entry(
    entity_id: str,
    date: str,
    description: str,
    debit_account_id: str,
    credit_account_id: str,
    amount: float,
    source_type: str | None = None,
    source_id: str | None = None,
) -> dict:
    return {
        "entity_id": entity_id,
        "date": date,
        "description": description,
        "source_type": source_type,
        "source_id": source_id,
        "status": "draft",
        "lines": [
            {"account_id": debit_account_id, "debit": amount, "credit": 0.0},
            {"account_id": credit_account_id, "debit": 0.0, "credit": amount},
        ],
    }


def build_invoice_issued_entry(entity_id: str, date: str, ar_account: str, revenue_account: str, amount: float, source_id: str) -> dict:
    return build_simple_journal_entry(
        entity_id, date, "Invoice issued", ar_account, revenue_account, amount, "invoice", source_id
    )


def build_customer_payment_entry(entity_id: str, date: str, cash_account: str, ar_account: str, amount: float, source_id: str) -> dict:
    return build_simple_journal_entry(
        entity_id, date, "Customer payment received", cash_account, ar_account, amount, "payment", source_id
    )


def build_owner_draw_entry(entity_id: str, date: str, owner_draw_account: str, cash_account: str, amount: float, source_id: str | None = None) -> dict:
    return build_simple_journal_entry(
        entity_id, date, "Owner draw", owner_draw_account, cash_account, amount, "owner_draw", source_id
    )
```

---

# 9. Skill: `general_ledger_builder`

```yaml
name: general_ledger_builder
pack: accounting
mode: business
risk_level: low
description: Builds account ledgers from posted journal lines.
heartbeat:
  weekly: true
confirmation:
  required: false
```

```python
# apps/api/app/skills/accounting/ledger/general_ledger.py
from __future__ import annotations

import pandas as pd

from ..core.normal_balances import NORMAL_BALANCE


def build_general_ledger(journal_lines: list[dict], accounts: list[dict]) -> dict:
    lines = pd.DataFrame(journal_lines)
    acct = pd.DataFrame(accounts)

    if lines.empty:
        return {"accounts": [], "warnings": ["No journal lines."]}

    df = lines.merge(acct, left_on="account_id", right_on="id", how="left")
    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)

    ledgers = []
    for account_id, group in df.groupby("account_id"):
        account_type = group["type"].iloc[0]
        normal = NORMAL_BALANCE[account_type]
        group = group.copy()

        if normal == "debit":
            group["signed_amount"] = group["debit"] - group["credit"]
        else:
            group["signed_amount"] = group["credit"] - group["debit"]

        group = group.sort_values("date")
        group["running_balance"] = group["signed_amount"].cumsum()

        ledgers.append({
            "account_id": account_id,
            "account_name": group["name"].iloc[0],
            "account_type": account_type,
            "normal_balance": normal,
            "ending_balance": float(group["running_balance"].iloc[-1]),
            "lines": group.to_dict("records"),
        })

    return {"accounts": ledgers}
```

---

# 10. Skill: `trial_balance_generator`

```yaml
name: trial_balance_generator
pack: accounting
mode: business
risk_level: low
description: Produces trial balance and validates debit/credit equality.
heartbeat:
  weekly: true
memory:
  writes:
    - trial_balance_snapshot
```

```python
# apps/api/app/skills/accounting/ledger/trial_balance.py
from __future__ import annotations

import pandas as pd


def generate_trial_balance(journal_lines: list[dict], accounts: list[dict]) -> dict:
    lines = pd.DataFrame(journal_lines)
    acct = pd.DataFrame(accounts)

    if lines.empty:
        return {"rows": [], "balanced": True, "total_debits": 0.0, "total_credits": 0.0}

    df = lines.merge(acct, left_on="account_id", right_on="id", how="left")
    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)

    grouped = df.groupby(["account_id", "code", "name", "type"])[["debit", "credit"]].sum().reset_index()

    rows = []
    total_debits = 0.0
    total_credits = 0.0

    for _, row in grouped.iterrows():
        balance = float(row["debit"] - row["credit"])
        debit_balance = balance if balance >= 0 else 0.0
        credit_balance = abs(balance) if balance < 0 else 0.0
        total_debits += debit_balance
        total_credits += credit_balance

        rows.append({
            "account_id": row["account_id"],
            "code": row["code"],
            "name": row["name"],
            "type": row["type"],
            "debit_balance": round(debit_balance, 2),
            "credit_balance": round(credit_balance, 2),
        })

    return {
        "rows": rows,
        "total_debits": round(total_debits, 2),
        "total_credits": round(total_credits, 2),
        "balanced": round(total_debits, 2) == round(total_credits, 2),
    }
```

---

# 11. Skill: `income_statement_generator`

```yaml
name: income_statement_generator
pack: accounting
mode: business
risk_level: low
description: Generates deterministic income statement from ledger lines.
heartbeat:
  weekly: true
memory:
  reads:
    - reporting_preference
  writes:
    - income_statement_snapshot
confirmation:
  required: false
```

```python
# apps/api/app/skills/accounting/ledger/financial_statements.py
from __future__ import annotations

import pandas as pd

from ..core.normal_balances import NORMAL_BALANCE


def generate_income_statement(journal_lines: list[dict], accounts: list[dict]) -> dict:
    lines = pd.DataFrame(journal_lines)
    acct = pd.DataFrame(accounts)
    if lines.empty:
        return {"revenue": 0.0, "expenses": 0.0, "net_income": 0.0, "warnings": ["No ledger data."]}

    df = lines.merge(acct, left_on="account_id", right_on="id", how="left")
    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)

    income_df = df[df["type"] == "income"].copy()
    expense_df = df[df["type"] == "expense"].copy()

    revenue = float((income_df["credit"] - income_df["debit"]).sum())
    expenses = float((expense_df["debit"] - expense_df["credit"]).sum())
    net_income = revenue - expenses

    expenses_by_account = (
        expense_df.assign(amount=expense_df["debit"] - expense_df["credit"])
        .groupby("name")["amount"]
        .sum()
        .reset_index()
        .sort_values("amount", ascending=False)
        .to_dict("records")
    )

    return {
        "revenue": revenue,
        "expenses": expenses,
        "net_income": net_income,
        "expenses_by_account": expenses_by_account,
    }


def generate_balance_sheet(journal_lines: list[dict], accounts: list[dict]) -> dict:
    lines = pd.DataFrame(journal_lines)
    acct = pd.DataFrame(accounts)
    if lines.empty:
        return {"assets": 0.0, "liabilities": 0.0, "equity": 0.0, "balanced": True}

    df = lines.merge(acct, left_on="account_id", right_on="id", how="left")
    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)

    def signed(row):
        normal = NORMAL_BALANCE[row["type"]]
        return row["debit"] - row["credit"] if normal == "debit" else row["credit"] - row["debit"]

    df["balance"] = df.apply(signed, axis=1)

    assets = float(df[df["type"] == "asset"]["balance"].sum())
    liabilities = float(df[df["type"] == "liability"]["balance"].sum())
    equity = float(df[df["type"] == "equity"]["balance"].sum())

    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "balanced": round(assets, 2) == round(liabilities + equity, 2),
        "difference": round(assets - liabilities - equity, 2),
    }
```

---

# 12. Skill: `accounts_receivable_manager`

```yaml
name: accounts_receivable_manager
pack: accounting
mode: business
risk_level: medium
description: Tracks invoices, payments, and AR aging.
heartbeat:
  daily: true
memory:
  reads:
    - customer_revenue_rule
  writes:
    - customer_payment_pattern
confirmation:
  required_when:
    - marking_invoice_paid
    - creating_writeoff
```

```python
# apps/api/app/skills/accounting/workflows/ar.py
from __future__ import annotations

import pandas as pd


def calculate_ar_aging(invoices: list[dict], as_of_date: str) -> dict:
    df = pd.DataFrame(invoices)
    if df.empty:
        return {"buckets": {}, "rows": []}

    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
    df["open_amount"] = pd.to_numeric(df["open_amount"], errors="coerce").fillna(0.0)
    as_of = pd.to_datetime(as_of_date)
    df["days_past_due"] = (as_of - df["due_date"]).dt.days

    def bucket(days: int) -> str:
        if days <= 0:
            return "current"
        if days <= 30:
            return "1_30"
        if days <= 60:
            return "31_60"
        if days <= 90:
            return "61_90"
        return "90_plus"

    df["bucket"] = df["days_past_due"].apply(bucket)
    buckets = df.groupby("bucket")["open_amount"].sum().to_dict()
    return {"buckets": buckets, "rows": df.to_dict("records")}
```

---

# 13. Skill: `accounts_payable_manager`

```yaml
name: accounts_payable_manager
pack: accounting
mode: business
risk_level: medium
description: Tracks vendor bills, due dates, and AP aging.
heartbeat:
  daily: true
memory:
  reads:
    - vendor_accounting_rule
  writes:
    - vendor_payment_pattern
confirmation:
  required_when:
    - marking_bill_paid
    - creating_payment_entry
```

```python
# apps/api/app/skills/accounting/workflows/ap.py
from __future__ import annotations

import pandas as pd


def calculate_ap_aging(bills: list[dict], as_of_date: str) -> dict:
    df = pd.DataFrame(bills)
    if df.empty:
        return {"buckets": {}, "rows": []}

    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
    df["open_amount"] = pd.to_numeric(df["open_amount"], errors="coerce").fillna(0.0)
    as_of = pd.to_datetime(as_of_date)
    df["days_past_due"] = (as_of - df["due_date"]).dt.days

    def bucket(days: int) -> str:
        if days <= 0:
            return "current"
        if days <= 30:
            return "1_30"
        if days <= 60:
            return "31_60"
        if days <= 90:
            return "61_90"
        return "90_plus"

    df["bucket"] = df["days_past_due"].apply(bucket)
    buckets = df.groupby("bucket")["open_amount"].sum().to_dict()
    return {"buckets": buckets, "rows": df.to_dict("records")}
```

---

# 14. Skill: `bank_reconciliation_assistant`

```yaml
name: bank_reconciliation_assistant
pack: accounting
mode: business
risk_level: high
description: Matches bank transactions to ledger cash entries and identifies differences.
heartbeat:
  weekly: true
confirmation:
  required_when:
    - creating_missing_entry
    - clearing_transaction
```

```python
# apps/api/app/skills/accounting/workflows/bank_reconciliation.py
from __future__ import annotations

import pandas as pd


def reconcile_bank_to_ledger(
    bank_transactions: list[dict],
    ledger_cash_entries: list[dict],
    tolerance: float = 0.01,
) -> dict:
    bank = pd.DataFrame(bank_transactions)
    ledger = pd.DataFrame(ledger_cash_entries)

    if bank.empty:
        return {"matched": [], "unmatched_bank": [], "unmatched_ledger": ledger_cash_entries}
    if ledger.empty:
        return {"matched": [], "unmatched_bank": bank_transactions, "unmatched_ledger": []}

    bank["amount"] = pd.to_numeric(bank["amount"], errors="coerce").fillna(0.0)
    ledger["amount"] = pd.to_numeric(ledger["amount"], errors="coerce").fillna(0.0)

    matched = []
    used_ledger = set()

    for bank_idx, bank_row in bank.iterrows():
        candidates = ledger[
            (~ledger.index.isin(used_ledger))
            & ((ledger["amount"] - bank_row["amount"]).abs() <= tolerance)
        ]
        if not candidates.empty:
            ledger_idx = candidates.index[0]
            used_ledger.add(ledger_idx)
            matched.append({
                "bank_transaction": bank_row.to_dict(),
                "ledger_entry": ledger.loc[ledger_idx].to_dict(),
            })

    unmatched_bank = bank.drop([m["bank_transaction"].get("index") for m in []], errors="ignore")
    unmatched_ledger = ledger[~ledger.index.isin(used_ledger)]

    matched_bank_ids = [m["bank_transaction"].get("id") for m in matched]
    if "id" in bank.columns:
        unmatched_bank = bank[~bank["id"].isin(matched_bank_ids)]

    return {
        "matched": matched,
        "unmatched_bank": unmatched_bank.to_dict("records"),
        "unmatched_ledger": unmatched_ledger.to_dict("records"),
    }
```

---

# 15. Skill: `fixed_asset_depreciation_assistant`

```yaml
name: fixed_asset_depreciation_assistant
pack: accounting
mode: business
risk_level: medium
description: Calculates depreciation and creates draft adjusting entries.
heartbeat:
  monthly: true
confirmation:
  required_when:
    - posting_depreciation_entry
```

```python
# apps/api/app/skills/accounting/workflows/depreciation.py
from __future__ import annotations


def straight_line_depreciation(cost: float, salvage_value: float, useful_life_months: int) -> dict:
    if useful_life_months <= 0:
        raise ValueError("useful_life_months must be positive")

    depreciable_base = max(cost - salvage_value, 0.0)
    monthly_depreciation = depreciable_base / useful_life_months

    return {
        "cost": cost,
        "salvage_value": salvage_value,
        "useful_life_months": useful_life_months,
        "depreciable_base": depreciable_base,
        "monthly_depreciation": monthly_depreciation,
    }
```

---

# 16. Skill: `accounting_question_generator`

```yaml
name: accounting_question_generator
pack: accounting
mode: business
risk_level: medium
description: Creates accounting questions for ambiguous items.
heartbeat:
  daily: true
memory:
  reads:
    - unresolved_accounting_pattern
  writes:
    - unresolved_accounting_pattern
confirmation:
  required: false
```

```python
# apps/api/app/skills/accounting/workflows/questions.py
from __future__ import annotations


def generate_accounting_question(record: dict, reason_codes: list[str]) -> dict:
    amount = record.get("amount")
    description = record.get("description") or record.get("merchant") or "this item"

    question = f"How should I classify {description} for {amount}?"

    if "personal_business_ambiguous" in reason_codes:
        question = f"Is {description} personal or business?"
    elif "owner_draw_possible" in reason_codes:
        question = f"Is {description} an owner draw, payroll, reimbursement, loan, or something else?"
    elif "asset_vs_expense" in reason_codes:
        question = f"Should {description} be expensed now or recorded as an asset?"

    return {
        "record_id": record.get("id"),
        "question": question,
        "reason_codes": reason_codes,
        "status": "open",
    }
```

---

# 17. Monthly Close Skill

```yaml
name: monthly_close_assistant
pack: accounting
mode: business
risk_level: high
description: Runs the accounting close checklist.
heartbeat:
  monthly: true
confirmation:
  required_when:
    - marking_period_closed
```

```python
# apps/api/app/skills/accounting/ledger/close.py
from __future__ import annotations


def build_monthly_close_checklist(context: dict) -> dict:
    checks = [
        "all_bank_imports_reviewed",
        "all_receipts_attached",
        "low_confidence_entries_resolved",
        "trial_balance_balanced",
        "ar_reviewed",
        "ap_reviewed",
        "bank_reconciliation_completed",
        "adjusting_entries_reviewed",
        "income_statement_generated",
        "balance_sheet_generated",
        "owner_draws_reviewed",
        "tax_reserve_reviewed",
        "reports_approved",
    ]

    items = []
    for check in checks:
        items.append({
            "check": check,
            "status": "pending" if not context.get(check) else "done",
        })

    can_close = all(item["status"] == "done" for item in items)
    return {"items": items, "can_close": can_close}
```

---

# 18. Heartbeat Plan

```yaml
daily:
  - journal_entry_validator
  - accounting_question_generator
  - accounts_receivable_manager
  - accounts_payable_manager

weekly:
  - trial_balance_generator
  - income_statement_generator
  - balance_sheet_generator
  - bank_reconciliation_assistant

monthly:
  - fixed_asset_depreciation_assistant
  - accrual_adjustment_assistant
  - closing_entries_assistant
  - monthly_close_assistant
```

---

# 19. Agent Routing Rules

```yaml
routing:
  user_wants_record_expense:
    call:
      - journal_entry_builder
      - journal_entry_validator
  user_asks_profit:
    call:
      - income_statement_generator
  user_asks_balance:
    call:
      - balance_sheet_generator
  user_asks_close_month:
    call:
      - monthly_close_assistant
  user_uploads_bill:
    call:
      - journal_entry_builder
      - accounts_payable_manager
      - accounting_question_generator_if_uncertain
```

---

# 20. Tests

```txt
test_journal_entry_balanced
test_journal_entry_unbalanced_rejected
test_debit_and_credit_same_line_rejected
test_general_ledger_running_balance
test_trial_balance_balanced
test_income_statement_net_income
test_balance_sheet_equation
test_ar_aging
test_ap_aging
test_bank_reconciliation
test_depreciation
test_owner_draw_entry
test_accounting_question_generation
test_monthly_close_blocks_open_items
test_audit_events_created
```

---

# 21. Acceptance Criteria

```txt
- Posted entries are balanced.
- Posted entries are immutable.
- Trial balance works.
- General ledger works.
- Income statement works.
- Balance sheet works.
- AR/AP aging works.
- Bank reconciliation workflow exists.
- Adjusting and closing workflows exist.
- Owner draws require careful review.
- Accounting questions are logged.
- User answers can become approved memory.
- Heartbeat reviews accounting health.
```
