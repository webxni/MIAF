from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.errors import FinClawError
from app.models import Account, DebtKind, GoalKind, InvestmentAccountKind, JournalEntryStatus
from app.schemas.journal import JournalEntryCreate, JournalLineIn
from app.schemas.personal import (
    BudgetCreate,
    DebtCreate,
    GoalCreate,
    InvestmentAccountCreate,
    InvestmentHoldingIn,
)
from app.services.journal import create_draft, post_entry
from app.services.personal import (
    create_budget,
    create_debt,
    create_goal,
    create_investment_account,
    personal_dashboard,
)


pytestmark = pytest.mark.asyncio


async def _accounts(db, entity_id: uuid.UUID) -> dict[str, Account]:
    rows = (
        await db.execute(select(Account).where(Account.entity_id == entity_id))
    ).scalars().all()
    return {a.code: a for a in rows}


async def _post(db, entity_id: uuid.UUID, user_id: uuid.UUID, payload: JournalEntryCreate) -> None:
    entry = await create_draft(db, entity_id=entity_id, user_id=user_id, payload=payload)
    posted = await post_entry(db, entry, posted_by_id=user_id)
    assert posted.status in (JournalEntryStatus.posted, JournalEntryStatus.voided)


async def test_budget_and_goal_can_be_created(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    accounts = await _accounts(db, entity_id)

    budget = await create_budget(
        db,
        entity_id=entity_id,
        payload=BudgetCreate(
            name="May 2026",
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
            lines=[{"account_id": accounts["5200"].id, "planned_amount": "500.00"}],
        ),
    )
    goal = await create_goal(
        db,
        entity_id=entity_id,
        payload=GoalCreate(
            name="Emergency Fund",
            kind=GoalKind.emergency_fund,
            target_amount=Decimal("3000.00"),
            linked_account_id=accounts["1130"].id,
        ),
    )

    assert budget.name == "May 2026"
    assert len(budget.lines) == 1
    assert goal.linked_account_id == accounts["1130"].id


async def test_debt_and_investment_creation_require_confirmation(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    accounts = await _accounts(db, entity_id)

    with pytest.raises(FinClawError) as debt_exc:
        await create_debt(
            db,
            entity_id=entity_id,
            payload=DebtCreate(
                name="Visa",
                kind=DebtKind.credit_card,
                current_balance=Decimal("900.00"),
                linked_account_id=accounts["2100"].id,
            ),
        )
    assert debt_exc.value.code == "confirmation_required"

    with pytest.raises(FinClawError) as investment_exc:
        await create_investment_account(
            db,
            entity_id=entity_id,
            payload=InvestmentAccountCreate(
                name="Brokerage",
                kind=InvestmentAccountKind.taxable_brokerage,
                linked_account_id=accounts["1200"].id,
            ),
        )
    assert investment_exc.value.code == "confirmation_required"


async def test_personal_dashboard_kpis_are_deterministic(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)

    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 2),
            memo="Salary",
            lines=[
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("3000.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["4100"].id, debit=Decimal("0"), credit=Decimal("3000.00")),
            ],
        ),
    )
    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 10),
            memo="Groceries",
            lines=[
                JournalLineIn(account_id=accounts["5200"].id, debit=Decimal("1200.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("0"), credit=Decimal("1200.00")),
            ],
        ),
    )
    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 15),
            memo="Save cash",
            lines=[
                JournalLineIn(account_id=accounts["1130"].id, debit=Decimal("600.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("0"), credit=Decimal("600.00")),
            ],
        ),
    )
    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 5),
            memo="Credit card opening balance",
            lines=[
                JournalLineIn(account_id=accounts["3100"].id, debit=Decimal("900.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["2100"].id, debit=Decimal("0"), credit=Decimal("900.00")),
            ],
        ),
    )

    await create_goal(
        db,
        entity_id=entity_id,
        payload=GoalCreate(
            name="Emergency Fund",
            kind=GoalKind.emergency_fund,
            target_amount=Decimal("3000.00"),
            linked_account_id=accounts["1130"].id,
        ),
    )
    await create_debt(
        db,
        entity_id=entity_id,
        payload=DebtCreate(
            confirmed=True,
            name="Visa",
            kind=DebtKind.credit_card,
            current_balance=Decimal("900.00"),
            linked_account_id=accounts["2100"].id,
        ),
    )
    await create_investment_account(
        db,
        entity_id=entity_id,
        payload=InvestmentAccountCreate(
            confirmed=True,
            name="Brokerage",
            kind=InvestmentAccountKind.taxable_brokerage,
            linked_account_id=accounts["1200"].id,
            holdings=[
                InvestmentHoldingIn(
                    symbol="VTI",
                    kind="etf",
                    shares=Decimal("10"),
                    current_price=Decimal("25"),
                )
            ],
        ),
    )

    dashboard = await personal_dashboard(db, entity_id=entity_id, as_of=date(2026, 5, 31))

    assert dashboard.monthly_income == Decimal("3000.00")
    assert dashboard.monthly_expenses == Decimal("1200.00")
    assert dashboard.monthly_savings == Decimal("1800.00")
    assert dashboard.savings_rate == Decimal("0.60")
    assert dashboard.emergency_fund_balance == Decimal("600.00")
    assert dashboard.emergency_fund_months == Decimal("0.50")
    assert dashboard.net_worth == Decimal("900.00")
    assert dashboard.total_debt == Decimal("900.00")
    assert dashboard.debt_to_income_ratio == Decimal("0.30")
    assert dashboard.investment_value == Decimal("250.00")
    assert dashboard.investment_allocation[0].label == "etf"
    assert dashboard.goal_progress[0].progress_ratio == Decimal("0.20")
    assert "does not execute trades" in dashboard.investment_disclaimer
