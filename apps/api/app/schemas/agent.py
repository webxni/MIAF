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


class AgentChatRequest(BaseModel):
    message: str = Field(default="", max_length=4000)
    entity_id: uuid.UUID | None = None
    confirmations: list[ToolConfirmationIn] = Field(default_factory=list)
    provider: str | None = Field(default=None, max_length=50)


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


class GenericToolResult(BaseModel):
    model_config = ConfigDict(extra="allow")

