from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPK


class TailscaleMode(str, enum.Enum):
    off = "off"
    direct_ip = "direct_ip"
    serve = "serve"


class TailscaleSettings(UUIDPK, Timestamps, Base):
    __tablename__ = "tailscale_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tailscale_settings_tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tailscale_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    tailscale_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TailscaleMode.off.value, server_default="off"
    )
    tailscale_target_url: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="http://127.0.0.1:80",
        server_default="http://127.0.0.1:80",
    )
    tailscale_hostname: Mapped[str | None] = mapped_column(String(253))
    tailscale_tailnet_url: Mapped[str | None] = mapped_column(String(500))
    tailscale_last_status: Mapped[str | None] = mapped_column(Text)
    tailscale_last_checked_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tailscale_setup_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    tailscale_notes: Mapped[str | None] = mapped_column(Text)
