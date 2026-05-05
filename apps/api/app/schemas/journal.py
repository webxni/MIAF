from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import JournalEntryStatus


class JournalLineIn(BaseModel):
    account_id: uuid.UUID
    debit: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    credit: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("debit", "credit", mode="before")
    @classmethod
    def _coerce_decimal(cls, v):
        if v is None or v == "":
            return Decimal("0")
        return Decimal(str(v))


class JournalEntryCreate(BaseModel):
    entry_date: date
    memo: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=100)
    lines: list[JournalLineIn] = Field(min_length=2)
    linked_entry_id: uuid.UUID | None = None
    source_transaction_id: uuid.UUID | None = None


class JournalEntryUpdate(BaseModel):
    entry_date: date | None = None
    memo: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=100)
    lines: list[JournalLineIn] | None = Field(default=None, min_length=2)


class JournalLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    line_no: int
    debit: Decimal
    credit: Decimal
    description: str | None


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    entry_date: date
    memo: str | None
    reference: str | None
    status: JournalEntryStatus
    posted_at: datetime | None
    posted_by_id: uuid.UUID | None
    voided_at: datetime | None
    voided_by_id: uuid.UUID | None
    voided_reason: str | None
    voided_by_entry_id: uuid.UUID | None
    voids_entry_id: uuid.UUID | None
    linked_entry_id: uuid.UUID | None
    source_transaction_id: uuid.UUID | None
    lines: list[JournalLineOut]


class VoidRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
