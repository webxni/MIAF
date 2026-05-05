from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models import EntityMode, Role


class EntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mode: EntityMode
    currency: str = Field(default="USD", min_length=3, max_length=3)


class EntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    mode: EntityMode
    currency: str


class EntityMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    user_id: uuid.UUID
    role: Role
