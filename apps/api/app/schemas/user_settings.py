from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AIProvider = Literal["heuristic", "anthropic", "openai", "gemini"]


class UserSettingsUpdate(BaseModel):
    jurisdiction: str | None = Field(default=None, max_length=64)
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    fiscal_year_start_month: int | None = Field(default=None, ge=1, le=12)
    ai_provider: AIProvider | None = None
    ai_model: str | None = Field(default=None, max_length=64)
    ai_api_key: str | None = Field(default=None, min_length=1, max_length=4000)
    ai_api_key_clear: bool = False

    @model_validator(mode="after")
    def validate_api_key_flags(self) -> "UserSettingsUpdate":
        if self.ai_api_key_clear and self.ai_api_key is not None:
            raise ValueError("Provide either ai_api_key or ai_api_key_clear, not both")
        return self


class UserSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    jurisdiction: str | None
    base_currency: str | None
    fiscal_year_start_month: int | None
    ai_provider: AIProvider | None
    ai_model: str | None
    ai_api_key_hint: str | None
    ai_api_key_present: bool
    created_at: datetime
    updated_at: datetime
