from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_decimal(value):
    if value is None or value == "":
        return None
    return Decimal(str(value))


class ToolConfirmationIn(BaseModel):
    tool_name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=0, max_length=8000)


class AgentChatRequest(BaseModel):
    message: str = Field(default="", max_length=4000)
    entity_id: uuid.UUID | None = None
    confirmations: list[ToolConfirmationIn] = Field(default_factory=list)
    provider: str | None = Field(default=None, max_length=50)
    conversation_history: list[ConversationMessage] = Field(default_factory=list, max_length=40)


class AgentToolCallOut(BaseModel):
    tool_name: str
    status: Literal["completed", "confirmation_required", "blocked", "not_implemented"]
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


class PendingConfirmationOut(BaseModel):
    tool_name: str
    reason: str
    arguments: dict[str, Any]


class AgentChatResponse(BaseModel):
    message: str
    provider: str
    tool_calls: list[AgentToolCallOut]
    pending_confirmations: list[PendingConfirmationOut]
    disclaimers: list[str] = Field(default_factory=list)


class CreatePersonalExpenseArgs(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2)
    description: str = Field(min_length=1, max_length=500)
    category_hint: str | None = Field(default=None, max_length=100)
    entry_date: date

    _coerce_amount = field_validator("amount", mode="before")(_to_decimal)


class CreateJournalEntryDraftArgs(BaseModel):
    entity_id: uuid.UUID
    entry_date: date
    memo: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=100)
    lines: list[dict[str, Any]] = Field(min_length=2)


class PostJournalEntryArgs(BaseModel):
    entity_id: uuid.UUID
    entry_id: uuid.UUID


class CreateInvoiceArgs(BaseModel):
    customer_name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0, decimal_places=2)
    description: str = Field(min_length=1, max_length=500)
    invoice_date: date
    due_date: date

    _coerce_amount = field_validator("amount", mode="before")(_to_decimal)


class SummaryArgs(BaseModel):
    as_of: date


class StatementArgs(BaseModel):
    as_of: date


class CashFlowArgs(BaseModel):
    date_from: date
    date_to: date


class SuggestEmergencyFundPlanArgs(BaseModel):
    as_of: date


class SuggestInvestmentAllocationArgs(BaseModel):
    as_of: date
    risk_profile: str | None = Field(default=None, max_length=100)


class ExplainTransactionArgs(BaseModel):
    description: str = Field(min_length=1, max_length=500)


class MemoryArgs(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class AnalyzeSpendingArgs(BaseModel):
    as_of: date
    limit: int = Field(default=90, ge=1, le=365)


class CheckFinancialHealthArgs(BaseModel):
    as_of: date


class SimulateGoalArgs(BaseModel):
    starting_balance: float = Field(default=0.0, ge=0)
    monthly_contribution: float = Field(default=0.0, ge=0)
    months: int = Field(default=12, ge=1, le=600)
    expected_monthly_return: float = Field(default=0.0)
    monthly_volatility: float = Field(default=0.0, ge=0)
    goal_amount: float | None = None


class ValidateJournalArgs(BaseModel):
    lines: list[dict]


class RecordInvoicePaymentArgs(BaseModel):
    invoice_id: uuid.UUID
    amount: Decimal = Field(gt=0, decimal_places=2)
    payment_date: date
    reference: str | None = Field(default=None, max_length=100)

    _coerce_amount = field_validator("amount", mode="before")(_to_decimal)


class CreateBillArgs(BaseModel):
    vendor_name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0, decimal_places=2)
    description: str = Field(min_length=1, max_length=500)
    bill_date: date
    due_date: date

    _coerce_amount = field_validator("amount", mode="before")(_to_decimal)


class RecordBillPaymentArgs(BaseModel):
    bill_id: uuid.UUID
    amount: Decimal = Field(gt=0, decimal_places=2)
    payment_date: date
    reference: str | None = Field(default=None, max_length=100)

    _coerce_amount = field_validator("amount", mode="before")(_to_decimal)


class CreateBudgetAgentArgs(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    period_start: date
    period_end: date
    notes: str | None = Field(default=None, max_length=500)


class CreateGoalAgentArgs(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_amount: Decimal = Field(gt=0, decimal_places=2)
    target_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)

    _coerce_amount = field_validator("target_amount", mode="before")(_to_decimal)


class CreateDebtPlanAgentArgs(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    current_balance: Decimal = Field(ge=0, decimal_places=2)
    interest_rate_apr: Decimal | None = Field(default=None, ge=0)
    minimum_payment: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    notes: str | None = Field(default=None, max_length=500)

    _coerce = field_validator("current_balance", "interest_rate_apr", "minimum_payment", mode="before")(_to_decimal)


# ── Skill-backed analytics tools ────────────────────────────────────────────

class JournalLinesArgs(BaseModel):
    """Accepts raw journal lines + account list for deterministic accounting reports."""
    journal_lines: list[dict] = Field(default_factory=list)
    accounts: list[dict] = Field(default_factory=list)


class TransactionsListArgs(BaseModel):
    transactions: list[dict] = Field(default_factory=list)


class BudgetVarianceArgs(BaseModel):
    budget_lines: list[dict] = Field(default_factory=list)
    actual_by_category: dict = Field(default_factory=dict)


class RoomForErrorArgs(BaseModel):
    profile: dict = Field(default_factory=dict)


class ReturnsListArgs(BaseModel):
    returns: list[float] = Field(default_factory=list)
    confidence_level: float = Field(default=0.95, ge=0.5, le=0.999)


class AnomalyRecordsArgs(BaseModel):
    records: list[dict] = Field(default_factory=list)
    group_col: str = Field(default="category")
    z_threshold: float = Field(default=2.5, ge=0.5)


class ChartDataArgs(BaseModel):
    chart_type: str = Field(default="line", max_length=20)
    title: str = Field(default="Chart", max_length=200)
    rows: list[dict] = Field(default_factory=list)
    x_key: str = Field(default="period")
    y_key: str = Field(default="value")
    label_key: str = Field(default="label")
    value_key: str = Field(default="value")


class MoneyMeetingContextArgs(BaseModel):
    context: dict = Field(default_factory=dict)


class AccountingQuestionArgs(BaseModel):
    record: dict = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)


class GenericToolResult(BaseModel):
    model_config = ConfigDict(extra="allow")

