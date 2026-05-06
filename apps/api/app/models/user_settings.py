from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPK


class UserSettings(UUIDPK, Timestamps, Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_settings_user_id"),
        CheckConstraint(
            "fiscal_year_start_month IS NULL OR fiscal_year_start_month BETWEEN 1 AND 12",
            name="fiscal_year_start_month_range",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jurisdiction: Mapped[str | None] = mapped_column(String(64))
    base_currency: Mapped[str | None] = mapped_column(String(3), nullable=True, default="USD", server_default="USD")
    fiscal_year_start_month: Mapped[int | None] = mapped_column(nullable=True, default=1, server_default="1")
    ai_provider: Mapped[str | None] = mapped_column(String(32))
    ai_model: Mapped[str | None] = mapped_column(String(64))
    ai_api_key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    ai_api_key_hint: Mapped[str | None] = mapped_column(String(8))
