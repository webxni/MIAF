from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    user_id: uuid.UUID | None
    entity_id: uuid.UUID | None
    action: str
    object_type: str
    object_id: str | None
    before: dict | None
    after: dict | None
    ip: str | None
    user_agent: str | None


class AuditLogListOut(BaseModel):
    rows: list[AuditLogOut]
    total: int
