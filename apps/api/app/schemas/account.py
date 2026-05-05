from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models import AccountType, NormalSide


class AccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    type: AccountType
    normal_side: NormalSide | None = None
    parent_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=500)


class AccountUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None
    is_active: bool | None = None
    description: str | None = Field(default=None, max_length=500)


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    parent_id: uuid.UUID | None
    code: str
    name: str
    type: AccountType
    normal_side: NormalSide
    is_active: bool
    description: str | None
