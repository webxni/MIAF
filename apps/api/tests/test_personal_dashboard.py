from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.errors import MIAFError
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
    budget_actuals,
    create_budget,
    create_debt,
    create_goal,
    create_investment_account,
    create_net_worth_snapshot,
    debt_payoff_plan,
    emergency_fund_plan,
    explain_net_worth_change,
    explain_spending_trends,
    investment_allocation_summary,
    list_net_worth_snapshots,
    monthly_cash_flow_report,
    net_worth_statement,
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

    with pytest.raises(MIAFError) as debt_exc:
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

    with pytest.raises(MIAFError) as investment_exc:
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
            entry_date=date(2026, 5, 1),
            memo="Owner draw received",
            lines=[
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("1000.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["4200"].id, debit=Decimal("0"), credit=Decimal("1000.00")),
            ],
        ),
    )
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

    assert dashboard.monthly_income == Decimal("4000.00")
    assert dashboard.monthly_expenses == Decimal("1200.00")
    assert dashboard.monthly_savings == Decimal("2800.00")
    assert dashboard.savings_rate == Decimal("0.70")
    assert dashboard.emergency_fund_balance == Decimal("600.00")
    assert dashboard.emergency_fund_months == Decimal("0.50")
    assert dashboard.net_worth == Decimal("1900.00")
    assert dashboard.total_debt == Decimal("900.00")
    assert dashboard.debt_to_income_ratio == Decimal("0.23")
    assert dashboard.cash_flow.total_cash_change == Decimal("2800.00")
    assert dashboard.spending_by_category[0].account_code == "5200"
    assert dashboard.spending_by_category[0].share_of_expenses == Decimal("1.00")
    assert dashboard.business_dependency.owner_draw_income == Decimal("1000.00")
    assert dashboard.business_dependency.salary_income == Decimal("3000.00")
    assert dashboard.business_dependency.business_dependency_ratio == Decimal("0.25")
    assert dashboard.business_dependency.depends_on_business_income is False
    assert dashboard.investment_value == Decimal("250.00")
    assert dashboard.investment_allocation[0].label == "etf"
    assert dashboard.goal_progress[0].progress_ratio == Decimal("0.20")
    assert "does not execute trades" in dashboard.investment_disclaimer


async def test_business_dependency_tracking_flags_owner_draw_dependence(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)

    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 3),
            memo="Owner draw received",
            lines=[
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("2000.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["4200"].id, debit=Decimal("0"), credit=Decimal("2000.00")),
            ],
        ),
    )
    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 4),
            memo="Part-time salary",
            lines=[
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("500.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["4100"].id, debit=Decimal("0"), credit=Decimal("500.00")),
            ],
        ),
    )

    dashboard = await personal_dashboard(db, entity_id=entity_id, as_of=date(2026, 5, 31))

    assert dashboard.business_dependency.owner_draw_income == Decimal("2000.00")
    assert dashboard.business_dependency.salary_income == Decimal("500.00")
    assert dashboard.business_dependency.business_dependency_ratio == Decimal("0.80")
    assert dashboard.business_dependency.dominant_source == "owner_draws"
    assert dashboard.business_dependency.depends_on_business_income is True


async def test_budget_actuals_exclude_savings_transfers_and_track_variance(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
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
    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 10),
            memo="Groceries",
            lines=[
                JournalLineIn(account_id=accounts["5200"].id, debit=Decimal("550.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("0"), credit=Decimal("550.00")),
            ],
        ),
    )
    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 15),
            memo="Move to emergency fund",
            lines=[
                JournalLineIn(account_id=accounts["1130"].id, debit=Decimal("200.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("0"), credit=Decimal("200.00")),
            ],
        ),
    )

    actuals = await budget_actuals(db, entity_id=entity_id, budget_id=budget.id)

    assert actuals.total_planned == Decimal("500.00")
    assert actuals.total_actual == Decimal("550.00")
    assert actuals.total_variance == Decimal("-50.00")
    assert actuals.lines[0].overspent is True
    assert actuals.lines[0].account_code == "5200"


async def test_net_worth_snapshot_persists_and_upserts(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)

    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 2),
            memo="Opening cash",
            lines=[
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("1000.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["3100"].id, debit=Decimal("0"), credit=Decimal("1000.00")),
            ],
        ),
    )
    snapshot = await create_net_worth_snapshot(db, entity_id=entity_id, as_of=date(2026, 5, 31))
    snapshots = await list_net_worth_snapshots(db, entity_id=entity_id, limit=12)

    assert snapshot.total_assets == Decimal("1000.00")
    assert snapshot.total_liabilities == Decimal("0.00")
    assert snapshot.net_worth == Decimal("1000.00")
    assert len(snapshots) == 1

    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 20),
            memo="Credit card balance",
            lines=[
                JournalLineIn(account_id=accounts["3100"].id, debit=Decimal("250.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["2100"].id, debit=Decimal("0"), credit=Decimal("250.00")),
            ],
        ),
    )
    updated = await create_net_worth_snapshot(db, entity_id=entity_id, as_of=date(2026, 5, 31))

    assert updated.id == snapshot.id
    assert updated.total_liabilities == Decimal("250.00")
    assert updated.net_worth == Decimal("750.00")


async def test_personal_phase11_reports_and_explanations(seeded, db):
    entity_id = uuid.UUID(seeded["personal_entity_id"])
    user_id = uuid.UUID(seeded["user_id"])
    accounts = await _accounts(db, entity_id)

    await create_debt(
        db,
        entity_id=entity_id,
        payload=DebtCreate(
            confirmed=True,
            name="Card A",
            kind=DebtKind.credit_card,
            current_balance=Decimal("400.00"),
            interest_rate_apr=Decimal("22.50"),
            minimum_payment=Decimal("40.00"),
        ),
    )
    await create_investment_account(
        db,
        entity_id=entity_id,
        payload=InvestmentAccountCreate(
            confirmed=True,
            name="Brokerage",
            kind=InvestmentAccountKind.taxable_brokerage,
            holdings=[
                InvestmentHoldingIn(
                    symbol="VTI",
                    kind="etf",
                    shares=Decimal("2"),
                    current_price=Decimal("100.00"),
                )
            ],
        ),
    )

    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 4, 10),
            memo="April salary",
            lines=[
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("1000.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["4100"].id, debit=Decimal("0"), credit=Decimal("1000.00")),
            ],
        ),
    )
    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 10),
            memo="May salary",
            lines=[
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("1200.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["4100"].id, debit=Decimal("0"), credit=Decimal("1200.00")),
            ],
        ),
    )
    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 12),
            memo="Dining",
            lines=[
                JournalLineIn(account_id=accounts["5200"].id, debit=Decimal("200.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("0"), credit=Decimal("200.00")),
            ],
        ),
    )
    await _post(
        db,
        entity_id,
        user_id,
        JournalEntryCreate(
            entry_date=date(2026, 5, 13),
            memo="Emergency fund transfer",
            lines=[
                JournalLineIn(account_id=accounts["1130"].id, debit=Decimal("300.00"), credit=Decimal("0")),
                JournalLineIn(account_id=accounts["1110"].id, debit=Decimal("0"), credit=Decimal("300.00")),
            ],
        ),
    )

    net_worth = await net_worth_statement(db, entity_id=entity_id, as_of=date(2026, 5, 31))
    cash_flow = await monthly_cash_flow_report(db, entity_id=entity_id, as_of=date(2026, 5, 31))
    payoff = await debt_payoff_plan(db, entity_id=entity_id, as_of=date(2026, 5, 31))
    emergency = await emergency_fund_plan(db, entity_id=entity_id, as_of=date(2026, 5, 31))
    allocation = await investment_allocation_summary(db, entity_id=entity_id, as_of=date(2026, 5, 31))
    nw_explanation = await explain_net_worth_change(
        db,
        entity_id=entity_id,
        date_from=date(2026, 4, 30),
        date_to=date(2026, 5, 31),
    )
    spending_explanation = await explain_spending_trends(db, entity_id=entity_id, as_of=date(2026, 5, 31))

    assert net_worth.net_worth == Decimal("2000.00")
    assert cash_flow.total_cash_change == Decimal("1000.00")
    assert payoff.strategy == "avalanche"
    assert payoff.total_debt == Decimal("400.00")
    assert emergency.target_min_balance == Decimal("600.00")
    assert emergency.current_coverage_months == Decimal("1.50")
    assert allocation.investment_value == Decimal("200.00")
    assert "change of" in nw_explanation.explanation
    assert any("Top current category" in fact for fact in spending_explanation.cited_facts)
