from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import AccountType, NormalSide


class LedgerLine(BaseModel):
    entry_id: uuid.UUID
    line_id: uuid.UUID
    entry_date: date
    memo: str | None
    reference: str | None
    debit: Decimal
    credit: Decimal
    description: str | None
    running_balance: Decimal


class LedgerResponse(BaseModel):
    account_id: uuid.UUID
    account_code: str
    account_name: str
    account_type: AccountType
    normal_side: NormalSide
    opening_balance: Decimal
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal
    lines: list[LedgerLine]


class TrialBalanceRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: uuid.UUID
    code: str
    name: str
    type: AccountType
    normal_side: NormalSide
    debit: Decimal
    credit: Decimal


class TrialBalanceResponse(BaseModel):
    entity_id: uuid.UUID
    as_of: date
    rows: list[TrialBalanceRow]
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool
