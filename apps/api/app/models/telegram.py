from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAt, Timestamps, UUIDPK
from app.models.entity import EntityMode


class TelegramMessageDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class TelegramMessageType(str, enum.Enum):
    text = "text"
    image = "image"
    pdf = "pdf"
    voice = "voice"
    command = "command"
    system = "system"


class TelegramMessageStatus(str, enum.Enum):
    processed = "processed"
    rejected = "rejected"
    rate_limited = "rate_limited"


class TelegramLink(UUIDPK, Timestamps, Base):
    __tablename__ = "telegram_links"
    __table_args__ = (UniqueConstraint("telegram_user_id", name="uq_telegram_links_telegram_user_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    personal_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    business_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    active_mode: Mapped[EntityMode] = mapped_column(
        SAEnum(EntityMode, name="telegram_active_mode"),
        nullable=False,
        default=EntityMode.personal,
    )
    telegram_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    telegram_chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    telegram_username: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TelegramMessage(UUIDPK, CreatedAt, Base):
    __tablename__ = "telegram_messages"

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
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    link_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("telegram_links.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    direction: Mapped[TelegramMessageDirection] = mapped_column(
        SAEnum(TelegramMessageDirection, name="telegram_message_direction"),
        nullable=False,
        index=True,
    )
    message_type: Mapped[TelegramMessageType] = mapped_column(
        SAEnum(TelegramMessageType, name="telegram_message_type"),
        nullable=False,
        index=True,
    )
    status: Mapped[TelegramMessageStatus] = mapped_column(
        SAEnum(TelegramMessageStatus, name="telegram_message_status"),
        nullable=False,
        default=TelegramMessageStatus.processed,
        index=True,
    )
    telegram_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    telegram_chat_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    telegram_message_id: Mapped[str | None] = mapped_column(String(64), index=True)
    text_body: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_mime_type: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict | None] = mapped_column(JSONB)
