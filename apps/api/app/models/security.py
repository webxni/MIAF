from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAt, UUIDPK


class LoginAttempt(UUIDPK, CreatedAt, Base):
    __tablename__ = "login_attempts"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), index=True)
    user_agent: Mapped[str | None] = mapped_column(String(512))
    was_successful: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    failure_reason: Mapped[str | None] = mapped_column(String(64), index=True)
