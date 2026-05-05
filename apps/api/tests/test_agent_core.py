from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.models import AuditLog, Customer, Invoice, JournalEntry, JournalEntryStatus, Session, User
from app.schemas.agent import AgentChatRequest
from app.services.agent import AgentService

pytestmark = pytest.mark.asyncio


async def _current_user(db, seeded) -> CurrentUser:
    user = await db.get(User, uuid.UUID(seeded["user_id"]))
    session = Session(
        user_id=user.id,
        token_hash=f"{uuid.uuid4().hex}{uuid.uuid4().hex}"[:64],
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(session)
    await db.flush()
    return CurrentUser(user=user, session=session)


async def test_agent_drafts_personal_expense_then_posts_after_confirmation(seeded, db):
    service = AgentService()
    me = await _current_user(db, seeded)

    first = await service.chat(
        db,
        me=me,
        payload=AgentChatRequest(message="Gasté $35 en gasolina personal."),
    )

    draft_call = next(call for call in first.tool_calls if call.tool_name == "create_personal_expense")
    assert draft_call.status == "completed"
    assert first.pending_confirmations

    draft_entry = await db.get(JournalEntry, uuid.UUID(draft_call.result["draft_entry_id"]))
    assert draft_entry is not None
    assert draft_entry.status == JournalEntryStatus.draft

    second = await service.chat(
        db,
        me=me,
        payload=AgentChatRequest(
            message="Confirm.",
            confirmations=[
                {
                    "tool_name": first.pending_confirmations[0].tool_name,
                    "arguments": first.pending_confirmations[0].arguments,
                }
            ],
        ),
    )

    post_call = next(call for call in second.tool_calls if call.tool_name == "post_journal_entry")
    assert post_call.status == "completed"
    await db.refresh(draft_entry)
    assert draft_entry.status == JournalEntryStatus.posted


async def test_agent_creates_business_invoice_draft_from_sale_phrase(seeded, db):
    service = AgentService()
    me = await _current_user(db, seeded)

    response = await service.chat(
        db,
        me=me,
        payload=AgentChatRequest(message="Mi negocio vendió $1,200 a Cliente X."),
    )

    invoice_call = next(call for call in response.tool_calls if call.tool_name == "create_invoice")
    assert invoice_call.status == "completed"
    invoice = await db.get(Invoice, uuid.UUID(invoice_call.result["invoice_id"]))
    customer = await db.get(Customer, uuid.UUID(invoice_call.result["customer_id"]))
    assert invoice is not None
    assert customer is not None
    assert customer.name == "Cliente X"
    assert invoice.total == Decimal("1200.00")


async def test_agent_explains_balance_sheet_with_deterministic_report(seeded, db):
    service = AgentService()
    me = await _current_user(db, seeded)

    response = await service.chat(
        db,
        me=me,
        payload=AgentChatRequest(message="Explain the balance sheet."),
    )

    call = next(call for call in response.tool_calls if call.tool_name == "get_balance_sheet")
    assert call.status == "completed"
    assert "total_assets" in call.result
    assert response.message


async def test_agent_compares_personal_and_business_summaries_and_audits(seeded, db):
    service = AgentService()
    me = await _current_user(db, seeded)

    response = await service.chat(
        db,
        me=me,
        payload=AgentChatRequest(message="Compare my personal and business cash flow."),
    )

    names = {call.tool_name for call in response.tool_calls}
    assert "get_personal_summary" in names
    assert "get_business_summary" in names

    audits = (await db.execute(select(AuditLog).where(AuditLog.object_type.in_(["agent", "get_personal_summary", "get_business_summary"])))).scalars().all()
    assert audits
