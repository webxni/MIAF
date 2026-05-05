from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import EntityMode, TelegramMessageDirection, TelegramMessageStatus, TelegramMessageType


class TelegramLinkCreate(BaseModel):
    telegram_user_id: str = Field(min_length=1, max_length=64)
    telegram_chat_id: str = Field(min_length=1, max_length=64)
    telegram_username: str | None = Field(default=None, max_length=100)
    personal_entity_id: uuid.UUID | None = None
    business_entity_id: uuid.UUID | None = None
    active_mode: EntityMode = EntityMode.personal
    is_active: bool = True


class TelegramLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    personal_entity_id: uuid.UUID | None
    business_entity_id: uuid.UUID | None
    active_mode: EntityMode
    telegram_user_id: str
    telegram_chat_id: str
    telegram_username: str | None
    is_active: bool
    last_seen_at: datetime | None


class TelegramInboundMessageIn(BaseModel):
    telegram_user_id: str = Field(min_length=1, max_length=64)
    telegram_chat_id: str = Field(min_length=1, max_length=64)
    telegram_message_id: str | None = Field(default=None, max_length=64)
    telegram_username: str | None = Field(default=None, max_length=100)
    message_type: TelegramMessageType
    text: str | None = Field(default=None, max_length=4000)
    file_name: str | None = Field(default=None, max_length=255)
    file_mime_type: str | None = Field(default=None, max_length=120)
    payload: dict = Field(default_factory=dict)


class TelegramWebhookResponse(BaseModel):
    accepted: bool
    reply_text: str
    active_mode: EntityMode | None = None
    routed_entity_id: uuid.UUID | None = None
    message_status: TelegramMessageStatus
    draft_entry_id: uuid.UUID | None = None


class TelegramMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    user_id: uuid.UUID | None
    entity_id: uuid.UUID | None
    link_id: uuid.UUID | None
    direction: TelegramMessageDirection
    message_type: TelegramMessageType
    status: TelegramMessageStatus
    telegram_user_id: str
    telegram_chat_id: str
    telegram_message_id: str | None
    text_body: str | None
    file_name: str | None
    file_mime_type: str | None
    payload: dict | None
    created_at: datetime
