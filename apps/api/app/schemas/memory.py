from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import MemoryEventType, MemoryReviewStatus, MemoryType


class MemoryCreate(BaseModel):
    memory_type: MemoryType
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=4000)
    summary: str | None = Field(default=None, max_length=500)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    source: str = Field(default="user", min_length=1, max_length=32)
    entity_id: uuid.UUID | None = None
    consent_granted: bool = False


class MemoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    summary: str | None = Field(default=None, max_length=500)
    keywords: list[str] | None = None
    is_active: bool | None = None


class MemoryReviewCreate(BaseModel):
    status: MemoryReviewStatus
    notes: str | None = Field(default=None, max_length=500)


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    entity_id: uuid.UUID | None
    memory_type: MemoryType
    title: str
    content: str
    summary: str | None
    keywords: list[str] | None
    source: str
    consent_granted: bool
    is_active: bool
    expires_at: datetime | None
    last_accessed_at: datetime | None


class MemoryEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    memory_id: uuid.UUID
    event_type: MemoryEventType
    payload: dict | None
    created_at: datetime


class MemoryReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    memory_id: uuid.UUID
    reviewer_user_id: uuid.UUID | None
    status: MemoryReviewStatus
    notes: str | None
    reviewed_at: datetime | None

