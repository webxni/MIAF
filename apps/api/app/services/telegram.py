from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.brand import AGENT_INTRO, SHORT_NAME
from app.errors import MIAFError, NotFoundError
from app.models import (
    Account,
    Entity,
    EntityMode,
    TelegramLink,
    TelegramMessage,
    TelegramMessageDirection,
    TelegramMessageStatus,
    TelegramMessageType,
    User,
)
from app.models.base import utcnow
from app.models.journal import JournalEntry
from app.schemas.agent import AgentChatRequest
from app.schemas.journal import JournalEntryCreate, JournalLineIn
from app.schemas.telegram import TelegramInboundMessageIn, TelegramLinkCreate, TelegramWebhookResponse
from app.services.agent import AgentService
from app.services.audit import write_audit
from app.services.business import business_dashboard
from app.services.journal import create_draft
from app.services.personal import personal_dashboard

_BUSINESS_EXPENSE_RE = re.compile(
    r"(?:negocio|business).*(?:pag[oó]|paid)\s+\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s+(?:de|for)?\s*(.+)",
    re.IGNORECASE,
)
_RATE_LIMIT_WINDOW = timedelta(minutes=1)
_RATE_LIMIT_MAX = 12


@dataclass
class RoutedContext:
    link: TelegramLink
    user: User
    entity_id: uuid.UUID | None


def _parse_amount(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def _business_category_to_code(text: str) -> str:
    normalized = text.lower()
    if "rent" in normalized or "alquiler" in normalized:
        return "6100"
    if any(token in normalized for token in ["utility", "utilities", "water", "electric", "luz"]):
        return "6200"
    if any(token in normalized for token in ["internet", "phone", "telefono"]):
        return "6300"
    if any(token in normalized for token in ["salary", "wage", "payroll", "nomina"]):
        return "6400"
    if any(token in normalized for token in ["office", "supplies", "papeleria"]):
        return "6500"
    return "6900"


async def _account_by_code(db: AsyncSession, *, entity_id: uuid.UUID, code: str) -> Account:
    row = (
        await db.execute(select(Account).where(Account.entity_id == entity_id, Account.code == code))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"Account {code} not found", code="account_not_found")
    return row


async def _validate_entity(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    mode: EntityMode,
) -> uuid.UUID | None:
    if entity_id is None:
        return None
    row = await db.get(Entity, entity_id)
    if row is None or row.tenant_id != tenant_id or row.mode != mode:
        raise NotFoundError(f"{mode.value.title()} entity {entity_id} not found", code="entity_not_found")
    return row.id


async def create_or_update_link(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: TelegramLinkCreate,
) -> TelegramLink:
    row = (
        await db.execute(select(TelegramLink).where(TelegramLink.telegram_user_id == payload.telegram_user_id))
    ).scalar_one_or_none()
    if row is None:
        row = TelegramLink(tenant_id=tenant_id, user_id=user_id, telegram_user_id=payload.telegram_user_id, telegram_chat_id=payload.telegram_chat_id)
        db.add(row)
    row.user_id = user_id
    row.tenant_id = tenant_id
    row.telegram_chat_id = payload.telegram_chat_id
    row.telegram_username = payload.telegram_username
    row.personal_entity_id = await _validate_entity(
        db, tenant_id=tenant_id, entity_id=payload.personal_entity_id, mode=EntityMode.personal
    )
    row.business_entity_id = await _validate_entity(
        db, tenant_id=tenant_id, entity_id=payload.business_entity_id, mode=EntityMode.business
    )
    row.active_mode = payload.active_mode
    row.is_active = payload.is_active
    await db.flush()
    await write_audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=None,
        action="upsert",
        object_type="telegram_link",
        object_id=row.id,
        after={"telegram_user_id": row.telegram_user_id, "active_mode": row.active_mode.value, "is_active": row.is_active},
    )
    return row


async def list_links(db: AsyncSession, *, tenant_id: uuid.UUID) -> list[TelegramLink]:
    return list(
        (
            await db.execute(
                select(TelegramLink).where(TelegramLink.tenant_id == tenant_id).order_by(TelegramLink.created_at.desc())
            )
        ).scalars().all()
    )


async def list_messages(db: AsyncSession, *, tenant_id: uuid.UUID, limit: int = 50) -> list[TelegramMessage]:
    return list(
        (
            await db.execute(
                select(TelegramMessage)
                .where(TelegramMessage.tenant_id == tenant_id)
                .order_by(TelegramMessage.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    )


async def process_inbound_message(
    db: AsyncSession,
    *,
    payload: TelegramInboundMessageIn,
) -> TelegramWebhookResponse:
    link = (
        await db.execute(
            select(TelegramLink).where(
                TelegramLink.telegram_user_id == payload.telegram_user_id,
                TelegramLink.telegram_chat_id == payload.telegram_chat_id,
                TelegramLink.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    user = await db.get(User, link.user_id) if link is not None else None
    routed_entity_id = _entity_for_link(link)

    inbound = TelegramMessage(
        tenant_id=link.tenant_id if link else None,
        user_id=user.id if user else None,
        entity_id=routed_entity_id,
        link_id=link.id if link else None,
        direction=TelegramMessageDirection.inbound,
        message_type=_normalize_message_type(payload),
        status=TelegramMessageStatus.processed if link else TelegramMessageStatus.rejected,
        telegram_user_id=payload.telegram_user_id,
        telegram_chat_id=payload.telegram_chat_id,
        telegram_message_id=payload.telegram_message_id,
        text_body=payload.text,
        file_name=payload.file_name,
        file_mime_type=payload.file_mime_type,
        payload=payload.payload,
    )
    db.add(inbound)
    await db.flush()

    if link is None or user is None:
        reply = "Telegram access is not enabled for this user."
        await _create_outbound_message(
            db,
            link=None,
            user=None,
            entity_id=None,
            telegram_user_id=payload.telegram_user_id,
            telegram_chat_id=payload.telegram_chat_id,
            reply_text=reply,
            status=TelegramMessageStatus.rejected,
            payload={"reason": "unknown_user"},
        )
        return TelegramWebhookResponse(
            accepted=False,
            reply_text=reply,
            active_mode=None,
            routed_entity_id=None,
            message_status=TelegramMessageStatus.rejected,
        )

    link.last_seen_at = utcnow()

    if await _is_rate_limited(db, link_id=link.id):
        reply = "Rate limit reached. Try again in a minute."
        inbound.status = TelegramMessageStatus.rate_limited
        await _create_outbound_message(
            db,
            link=link,
            user=user,
            entity_id=routed_entity_id,
            telegram_user_id=payload.telegram_user_id,
            telegram_chat_id=payload.telegram_chat_id,
            reply_text=reply,
            status=TelegramMessageStatus.rate_limited,
            payload={"reason": "rate_limited"},
        )
        await _write_telegram_audit(db, link=link, user=user, entity_id=routed_entity_id, direction="inbound", action="rate_limited")
        return TelegramWebhookResponse(
            accepted=False,
            reply_text=reply,
            active_mode=link.active_mode,
            routed_entity_id=routed_entity_id,
            message_status=TelegramMessageStatus.rate_limited,
        )

    reply_text, entity_id, draft_entry_id = await _handle_message(db, payload=payload, link=link, user=user)
    await _create_outbound_message(
        db,
        link=link,
        user=user,
        entity_id=entity_id,
        telegram_user_id=payload.telegram_user_id,
        telegram_chat_id=payload.telegram_chat_id,
        reply_text=reply_text,
        status=TelegramMessageStatus.processed,
        payload={"draft_entry_id": str(draft_entry_id) if draft_entry_id else None},
    )
    await _write_telegram_audit(db, link=link, user=user, entity_id=entity_id, direction="inbound", action="processed")
    await _write_telegram_audit(db, link=link, user=user, entity_id=entity_id, direction="outbound", action="reply_sent")
    return TelegramWebhookResponse(
        accepted=True,
        reply_text=reply_text,
        active_mode=link.active_mode,
        routed_entity_id=entity_id,
        message_status=TelegramMessageStatus.processed,
        draft_entry_id=draft_entry_id,
    )


async def _handle_message(
    db: AsyncSession,
    *,
    payload: TelegramInboundMessageIn,
    link: TelegramLink,
    user: User,
) -> tuple[str, uuid.UUID | None, uuid.UUID | None]:
    text = (payload.text or "").strip()
    if text.startswith("/"):
        return await _handle_command(db, link=link, command=text.lower())

    entity_id = _entity_for_link(link)
    if payload.message_type in {TelegramMessageType.image, TelegramMessageType.pdf}:
        return "Receipt or document received and queued for review.", entity_id, None
    if payload.message_type == TelegramMessageType.voice:
        return "Voice note received. Transcription review is still a placeholder.", entity_id, None

    if link.active_mode == EntityMode.business:
        expense = _BUSINESS_EXPENSE_RE.search(text)
        if expense and link.business_entity_id is not None:
            amount = _parse_amount(expense.group(1))
            description = expense.group(2).strip().rstrip(".")
            entry = await _create_business_expense_draft(db, entity_id=link.business_entity_id, user_id=user.id, amount=amount, description=description)
            return (
                f"Drafted business expense for {amount:.2f}. Confirm posting later from {SHORT_NAME} before it hits the ledger.",
                link.business_entity_id,
                entry.id,
            )

    service = AgentService()
    me = CurrentUser(user=user, session=None)  # type: ignore[arg-type]
    agent = await service.chat(db, me=me, payload=AgentChatRequest(message=text, entity_id=entity_id))
    return agent.message, entity_id, None


async def _handle_command(
    db: AsyncSession,
    *,
    link: TelegramLink,
    command: str,
) -> tuple[str, uuid.UUID | None, uuid.UUID | None]:
    if command == "/start":
        return (
            f"{AGENT_INTRO} Telegram is linked. Use /personal, /business, /summary, /budget, /cash, or /help.",
            _entity_for_link(link),
            None,
        )
    if command == "/personal":
        link.active_mode = EntityMode.personal
        return "Personal mode is active for this chat.", link.personal_entity_id, None
    if command == "/business":
        link.active_mode = EntityMode.business
        return "Business mode is active for this chat.", link.business_entity_id, None
    if command == "/help":
        return "Commands: /start, /personal, /business, /summary, /budget, /cash, /help", _entity_for_link(link), None
    if command == "/summary":
        entity_id = _entity_for_link(link)
        return await _render_summary(db, link=link), entity_id, None
    if command == "/cash":
        entity_id = _entity_for_link(link)
        return await _render_cash(db, link=link), entity_id, None
    if command == "/budget":
        entity_id = _entity_for_link(link)
        return await _render_budget(db, link=link), entity_id, None
    return "Unknown command. Use /help for the supported Telegram commands.", _entity_for_link(link), None


def _entity_for_link(link: TelegramLink | None) -> uuid.UUID | None:
    if link is None:
        return None
    return link.personal_entity_id if link.active_mode == EntityMode.personal else link.business_entity_id


def _normalize_message_type(payload: TelegramInboundMessageIn) -> TelegramMessageType:
    if (payload.text or "").strip().startswith("/"):
        return TelegramMessageType.command
    return payload.message_type


async def _is_rate_limited(db: AsyncSession, *, link_id: uuid.UUID) -> bool:
    since = utcnow() - _RATE_LIMIT_WINDOW
    rows = (
        await db.execute(
            select(TelegramMessage)
            .where(
                TelegramMessage.link_id == link_id,
                TelegramMessage.direction == TelegramMessageDirection.inbound,
                TelegramMessage.created_at >= since,
            )
            .order_by(TelegramMessage.created_at.desc())
        )
    ).scalars().all()
    return len(rows) > _RATE_LIMIT_MAX


async def _create_outbound_message(
    db: AsyncSession,
    *,
    link: TelegramLink | None,
    user: User | None,
    entity_id: uuid.UUID | None,
    telegram_user_id: str,
    telegram_chat_id: str,
    reply_text: str,
    status: TelegramMessageStatus,
    payload: dict,
) -> TelegramMessage:
    row = TelegramMessage(
        tenant_id=link.tenant_id if link else None,
        user_id=user.id if user else None,
        entity_id=entity_id,
        link_id=link.id if link else None,
        direction=TelegramMessageDirection.outbound,
        message_type=TelegramMessageType.text,
        status=status,
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        text_body=reply_text,
        payload=payload,
    )
    db.add(row)
    await db.flush()
    return row


async def _write_telegram_audit(
    db: AsyncSession,
    *,
    link: TelegramLink,
    user: User,
    entity_id: uuid.UUID | None,
    direction: str,
    action: str,
) -> None:
    await write_audit(
        db,
        tenant_id=link.tenant_id,
        user_id=user.id,
        entity_id=entity_id,
        action=action,
        object_type="telegram_message",
        object_id=link.id,
        after={"direction": direction, "active_mode": link.active_mode.value},
    )


async def _render_summary(db: AsyncSession, *, link: TelegramLink) -> str:
    as_of = date.today()
    if link.active_mode == EntityMode.personal and link.personal_entity_id is not None:
        dashboard = await personal_dashboard(db, entity_id=link.personal_entity_id, as_of=as_of)
        return (
            f"Personal summary: net worth {dashboard.net_worth}, savings rate {dashboard.savings_rate}, "
            f"emergency fund {dashboard.emergency_fund_months} months."
        )
    if link.business_entity_id is not None:
        dashboard = await business_dashboard(db, entity_id=link.business_entity_id, as_of=as_of)
        return (
            f"Business summary: cash {dashboard.cash_balance}, AR {dashboard.accounts_receivable}, "
            f"AP {dashboard.accounts_payable}, net income {dashboard.monthly_net_income}."
        )
    return "No entity is linked for the current Telegram mode."


async def _render_cash(db: AsyncSession, *, link: TelegramLink) -> str:
    as_of = date.today()
    if link.active_mode == EntityMode.personal and link.personal_entity_id is not None:
        dashboard = await personal_dashboard(db, entity_id=link.personal_entity_id, as_of=as_of)
        return f"Personal cash snapshot: monthly income {dashboard.monthly_income}, expenses {dashboard.monthly_expenses}, savings {dashboard.monthly_savings}."
    if link.business_entity_id is not None:
        dashboard = await business_dashboard(db, entity_id=link.business_entity_id, as_of=as_of)
        return f"Business cash snapshot: cash {dashboard.cash_balance}, revenue {dashboard.monthly_revenue}, expenses {dashboard.monthly_expenses}."
    return "No entity is linked for the current Telegram mode."


async def _render_budget(db: AsyncSession, *, link: TelegramLink) -> str:
    if link.active_mode != EntityMode.personal or link.personal_entity_id is None:
        return "Switch to /personal to review budget and spending context."
    dashboard = await personal_dashboard(db, entity_id=link.personal_entity_id, as_of=date.today())
    top = ", ".join(f"{row.label} {row.amount}" for row in dashboard.spending_by_category[:3]) or "no spending categories yet"
    return f"Budget snapshot: savings rate {dashboard.savings_rate}. Top spending categories: {top}."


async def _create_business_expense_draft(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    user_id: uuid.UUID,
    amount: Decimal,
    description: str,
) -> JournalEntry:
    cash = await _account_by_code(db, entity_id=entity_id, code="1110")
    expense = await _account_by_code(db, entity_id=entity_id, code=_business_category_to_code(description))
    entry = await create_draft(
        db,
        entity_id=entity_id,
        user_id=user_id,
        payload=JournalEntryCreate(
            entry_date=date.today(),
            memo=f"Telegram business expense: {description}",
            lines=[
                JournalLineIn(account_id=expense.id, debit=amount, description=description),
                JournalLineIn(account_id=cash.id, credit=amount, description=description),
            ],
        ),
    )
    return entry
