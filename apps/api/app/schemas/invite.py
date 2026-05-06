from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.entity import Role


class InviteCreate(BaseModel):
    email: EmailStr
    role: Role = Role.viewer


class AcceptInviteRequest(BaseModel):
    token: str
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8)


class InviteOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    is_revoked: bool
    created_at: datetime
