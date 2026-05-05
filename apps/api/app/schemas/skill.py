from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SkillManifestOut(BaseModel):
    name: str
    version: str
    description: str
    mode: Literal["personal", "business", "both"]
    permissions: list[str]
    triggers: list[str]
    tools_used: list[str]
    requires_confirmation: bool
    risk_level: Literal["low", "medium", "high"]
    entrypoint: str
    builtin: bool
    enabled: bool


class SkillToggleRequest(BaseModel):
    enabled: bool


class SkillRunRequest(BaseModel):
    entity_id: uuid.UUID | None = None
    input: dict = Field(default_factory=dict)


class SkillRunLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    entity_id: uuid.UUID | None
    skill_name: str
    skill_version: str
    permissions: list[str]
    input_payload: dict | None
    output_payload: dict | None
    result_status: str
    created_at: datetime
