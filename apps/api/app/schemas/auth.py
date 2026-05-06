from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1000)


class RegisterOwnerRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=1000)
    name: str = Field(min_length=1, max_length=100)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1000)
    new_password: str = Field(min_length=12, max_length=1000)


class UserOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    name: str

    class Config:
        from_attributes = True
