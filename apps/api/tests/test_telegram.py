from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models import EntityMode, JournalEntry, JournalEntryStatus, TelegramMessage, TelegramMessageStatus, TelegramMessageType
from app.schemas.telegram import TelegramInboundMessageIn, TelegramLinkCreate
from app.services.telegram import create_or_update_link, process_inbound_message

pytestmark = pytest.mark.asyncio


async def _link_payload(seeded) -> TelegramLinkCreate:
    return TelegramLinkCreate(
        telegram_user_id="tg-user-1",
        telegram_chat_id="tg-chat-1",
        telegram_username="owner_demo",
        personal_entity_id=uuid.UUID(seeded["personal_entity_id"]),
        business_entity_id=uuid.UUID(seeded["business_entity_id"]),
    )


async def test_unknown_telegram_user_is_rejected(seeded, db):
    result = await process_inbound_message(
        db,
        payload=TelegramInboundMessageIn(
            telegram_user_id="unknown",
            telegram_chat_id="chat-unknown",
            message_type=TelegramMessageType.text,
            text="/summary",
        ),
    )

    assert result.accepted is False
    assert result.message_status == TelegramMessageStatus.rejected


async def test_telegram_personal_expense_routes_through_agent(seeded, db):
    await create_or_update_link(
        db,
        tenant_id=uuid.UUID(seeded["tenant_id"]),
        user_id=uuid.UUID(seeded["user_id"]),
        payload=await _link_payload(seeded),
    )

    result = await process_inbound_message(
        db,
        payload=TelegramInboundMessageIn(
            telegram_user_id="tg-user-1",
            telegram_chat_id="tg-chat-1",
            message_type=TelegramMessageType.text,
            text="Gasté $20 en comida personal.",
        ),
    )

    assert result.accepted is True
    assert "confirmation" in result.reply_text.lower()
    messages = (await db.execute(select(TelegramMessage).order_by(TelegramMessage.created_at))).scalars().all()
    assert len(messages) == 2
    assert messages[0].direction.value == "inbound"
    assert messages[1].direction.value == "outbound"


async def test_telegram_business_expense_creates_draft_entry(seeded, db):
    link = await create_or_update_link(
        db,
        tenant_id=uuid.UUID(seeded["tenant_id"]),
        user_id=uuid.UUID(seeded["user_id"]),
        payload=(await _link_payload(seeded)).model_copy(update={"active_mode": EntityMode.business}),
    )

    result = await process_inbound_message(
        db,
        payload=TelegramInboundMessageIn(
            telegram_user_id="tg-user-1",
            telegram_chat_id="tg-chat-1",
            message_type=TelegramMessageType.text,
            text="El negocio pagó $150 de internet.",
        ),
    )

    assert result.accepted is True
    assert result.draft_entry_id is not None
    entry = await db.get(JournalEntry, result.draft_entry_id)
    assert entry is not None
    assert entry.status == JournalEntryStatus.draft


async def test_telegram_receipt_upload_is_logged_and_acknowledged(seeded, db):
    await create_or_update_link(
        db,
        tenant_id=uuid.UUID(seeded["tenant_id"]),
        user_id=uuid.UUID(seeded["user_id"]),
        payload=await _link_payload(seeded),
    )

    result = await process_inbound_message(
        db,
        payload=TelegramInboundMessageIn(
            telegram_user_id="tg-user-1",
            telegram_chat_id="tg-chat-1",
            message_type=TelegramMessageType.image,
            file_name="receipt.jpg",
            file_mime_type="image/jpeg",
        ),
    )

    assert result.accepted is True
    assert "queued for review" in result.reply_text.lower()


async def test_telegram_summary_command_returns_deterministic_summary(seeded, db):
    await create_or_update_link(
        db,
        tenant_id=uuid.UUID(seeded["tenant_id"]),
        user_id=uuid.UUID(seeded["user_id"]),
        payload=await _link_payload(seeded),
    )

    result = await process_inbound_message(
        db,
        payload=TelegramInboundMessageIn(
            telegram_user_id="tg-user-1",
            telegram_chat_id="tg-chat-1",
            message_type=TelegramMessageType.text,
            text="/summary",
        ),
    )

    assert result.accepted is True
    assert "summary" in result.reply_text.lower()
