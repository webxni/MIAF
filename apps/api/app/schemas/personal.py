from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    DebtKind,
    DebtStatus,
    GoalKind,
    GoalStatus,
    HoldingKind,
    InvestmentAccountKind,
)


def _to_decimal(value):
    if value is None or value == "":
        return None
    return Decimal(str(value))


class BudgetLineIn(BaseModel):
    account_id: uuid.UUID
    planned_amount: Decimal = Field(ge=0, decimal_places=2)
    notes: str | None = Field(default=None, max_length=500)

    _coerce_amount = field_validator("planned_amount", mode="before")(_to_decimal)


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    period_start: date
    period_end: date
    notes: str | None = Field(default=None, max_length=500)
    lines: list[BudgetLineIn] = Field(default_factory=list)


class BudgetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    period_start: date | None = None
    period_end: date | None = None
    notes: str | None = Field(default=None, max_length=500)
    lines: list[BudgetLineIn] | None = None


class BudgetLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    planned_amount: Decimal
    notes: str | None


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    name: str
    period_start: date
    period_end: date
    notes: str | None
    lines: list[BudgetLineOut]


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: GoalKind
    target_amount: Decimal = Field(gt=0, decimal_places=2)
    target_date: date | None = None
    current_amount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    linked_account_id: uuid.UUID | None = None
    status: GoalStatus = GoalStatus.active
    notes: str | None = Field(default=None, max_length=500)

    _target = field_validator("target_amount", "current_amount", mode="before")(_to_decimal)


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: GoalKind | None = None
    target_amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    target_date: date | None = None
    current_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    linked_account_id: uuid.UUID | None = None
    status: GoalStatus | None = None
    notes: str | None = Field(default=None, max_length=500)

    _target = field_validator("target_amount", "current_amount", mode="before")(_to_decimal)


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    name: str
    kind: GoalKind
    target_amount: Decimal
    target_date: date | None
    current_amount: Decimal
    linked_account_id: uuid.UUID | None
    status: GoalStatus
    notes: str | None


class DebtCreate(BaseModel):
    confirmed: bool = False
    name: str = Field(min_length=1, max_length=200)
    kind: DebtKind
    original_principal: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    current_balance: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    interest_rate_apr: Decimal | None = Field(default=None, ge=0)
    minimum_payment: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    due_day_of_month: int | None = Field(default=None, ge=1, le=31)
    next_due_date: date | None = None
    linked_account_id: uuid.UUID | None = None
    status: DebtStatus = DebtStatus.active
    notes: str | None = Field(default=None, max_length=500)

    _target = field_validator(
        "original_principal",
        "current_balance",
        "interest_rate_apr",
        "minimum_payment",
        mode="before",
    )(_to_decimal)


class DebtUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: DebtKind | None = None
    original_principal: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    current_balance: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    interest_rate_apr: Decimal | None = Field(default=None, ge=0)
    minimum_payment: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    due_day_of_month: int | None = Field(default=None, ge=1, le=31)
    next_due_date: date | None = None
    linked_account_id: uuid.UUID | None = None
    status: DebtStatus | None = None
    notes: str | None = Field(default=None, max_length=500)

    _target = field_validator(
        "original_principal",
        "current_balance",
        "interest_rate_apr",
        "minimum_payment",
        mode="before",
    )(_to_decimal)


class DebtOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    name: str
    kind: DebtKind
    original_principal: Decimal | None
    current_balance: Decimal
    interest_rate_apr: Decimal | None
    minimum_payment: Decimal | None
    due_day_of_month: int | None
    next_due_date: date | None
    linked_account_id: uuid.UUID | None
    status: DebtStatus
    notes: str | None


class InvestmentHoldingIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=200)
    kind: HoldingKind
    shares: Decimal = Field(default=Decimal("0"), ge=0)
    cost_basis_per_share: Decimal | None = Field(default=None, ge=0)
    current_price: Decimal | None = Field(default=None, ge=0)
    last_priced_at: datetime | None = None

    _target = field_validator(
        "shares",
        "cost_basis_per_share",
        "current_price",
        mode="before",
    )(_to_decimal)


class InvestmentAccountCreate(BaseModel):
    confirmed: bool = False
    name: str = Field(min_length=1, max_length=200)
    broker: str | None = Field(default=None, max_length=200)
    kind: InvestmentAccountKind
    currency: str = Field(default="USD", min_length=3, max_length=3)
    linked_account_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=500)
    holdings: list[InvestmentHoldingIn] = Field(default_factory=list)


class InvestmentAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    broker: str | None = Field(default=None, max_length=200)
    kind: InvestmentAccountKind | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    linked_account_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=500)
    holdings: list[InvestmentHoldingIn] | None = None


class InvestmentHoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    name: str | None
    kind: HoldingKind
    shares: Decimal
    cost_basis_per_share: Decimal | None
    current_price: Decimal | None
    last_priced_at: datetime | None


class InvestmentAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    name: str
    broker: str | None
    kind: InvestmentAccountKind
    currency: str
    linked_account_id: uuid.UUID | None
    notes: str | None
    holdings: list[InvestmentHoldingOut]


class GoalProgressOut(BaseModel):
    goal_id: uuid.UUID
    name: str
    kind: GoalKind
    target_amount: Decimal
    current_amount: Decimal
    progress_ratio: Decimal


class InvestmentAllocationRow(BaseModel):
    label: str
    value: Decimal
    allocation_ratio: Decimal


class PersonalDashboardOut(BaseModel):
    entity_id: uuid.UUID
    as_of: date
    month_start: date
    month_end: date
    net_worth: Decimal
    monthly_income: Decimal
    monthly_expenses: Decimal
    monthly_savings: Decimal
    savings_rate: Decimal
    emergency_fund_balance: Decimal
    emergency_fund_months: Decimal
    total_debt: Decimal
    debt_to_income_ratio: Decimal
    investment_value: Decimal
    investment_allocation: list[InvestmentAllocationRow]
    goal_progress: list[GoalProgressOut]
    investment_disclaimer: str
