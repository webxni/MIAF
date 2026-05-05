from __future__ import annotations

import calendar
import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import ConflictError, FinClawError, NotFoundError
from app.models import (
    Account,
    AccountType,
    Budget,
    BudgetLine,
    Debt,
    Entity,
    EntityMode,
    Goal,
    HoldingKind,
    InvestmentAccount,
    InvestmentHolding,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
    NormalSide,
)
from app.money import ZERO, to_money
from app.schemas.personal import (
    BudgetCreate,
    BudgetLineIn,
    BudgetUpdate,
    DebtCreate,
    DebtUpdate,
    GoalCreate,
    GoalProgressOut,
    GoalUpdate,
    InvestmentAccountCreate,
    InvestmentAccountUpdate,
    InvestmentAllocationRow,
    InvestmentHoldingIn,
    PersonalDashboardOut,
)

INVESTMENT_DISCLAIMER = (
    "Investment tracking is advisory only. FinClaw does not execute trades or guarantee returns."
)


async def _get_personal_entity(db: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = await db.get(Entity, entity_id)
    if entity is None:
        raise NotFoundError(f"Entity {entity_id} not found", code="entity_not_found")
    if entity.mode != EntityMode.personal:
        raise FinClawError(
            "This endpoint is only available for personal entities",
            code="entity_not_personal",
        )
    return entity


async def _get_account_map(
    db: AsyncSession, entity_id: uuid.UUID, account_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Account]:
    if not account_ids:
        return {}
    rows = (
        await db.execute(
            select(Account).where(
                Account.entity_id == entity_id,
                Account.id.in_(account_ids),
            )
        )
    ).scalars().all()
    out = {row.id: row for row in rows}
    missing = set(account_ids) - set(out)
    if missing:
        raise NotFoundError(
            f"Account(s) not found: {sorted(str(item) for item in missing)}",
            code="account_not_found",
        )
    return out


def _signed_balance(debit: Decimal, credit: Decimal, normal_side: NormalSide) -> Decimal:
    if normal_side == NormalSide.debit:
        return to_money(debit - credit)
    return to_money(credit - debit)


def _month_bounds(as_of: date) -> tuple[date, date]:
    start = as_of.replace(day=1)
    end = as_of.replace(day=calendar.monthrange(as_of.year, as_of.month)[1])
    return start, end


async def _account_balances(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[uuid.UUID, dict]:
    filters = [
        Account.entity_id == entity_id,
        JournalEntry.entity_id == entity_id,
        JournalEntry.status.in_([JournalEntryStatus.posted, JournalEntryStatus.voided]),
    ]
    if date_from is not None:
        filters.append(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        filters.append(JournalEntry.entry_date <= date_to)

    rows = (
        await db.execute(
            select(
                Account.id,
                Account.code,
                Account.name,
                Account.type,
                Account.normal_side,
                func.coalesce(func.sum(JournalLine.debit), 0).label("debit"),
                func.coalesce(func.sum(JournalLine.credit), 0).label("credit"),
            )
            .join(JournalLine, JournalLine.account_id == Account.id)
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(*filters)
            .group_by(Account.id)
        )
    ).all()

    out: dict[uuid.UUID, dict] = {}
    for row in rows:
        debit = Decimal(row.debit)
        credit = Decimal(row.credit)
        out[row.id] = {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "type": row.type,
            "normal_side": row.normal_side,
            "balance": _signed_balance(debit, credit, row.normal_side),
        }
    return out


async def list_budgets(db: AsyncSession, *, entity_id: uuid.UUID) -> list[Budget]:
    await _get_personal_entity(db, entity_id)
    rows = (
        await db.execute(
            select(Budget)
            .options(selectinload(Budget.lines))
            .where(Budget.entity_id == entity_id)
            .order_by(Budget.period_start.desc(), Budget.created_at.desc())
        )
    ).scalars()
    return list(rows)


async def get_budget(db: AsyncSession, *, entity_id: uuid.UUID, budget_id: uuid.UUID) -> Budget:
    await _get_personal_entity(db, entity_id)
    budget = (
        await db.execute(
            select(Budget)
            .options(selectinload(Budget.lines))
            .where(Budget.id == budget_id, Budget.entity_id == entity_id)
        )
    ).scalar_one_or_none()
    if budget is None:
        raise NotFoundError(f"Budget {budget_id} not found", code="budget_not_found")
    return budget


async def _replace_budget_lines(
    db: AsyncSession,
    budget: Budget,
    lines: list[BudgetLineIn],
) -> None:
    account_map = await _get_account_map(
        db, budget.entity_id, [line.account_id for line in lines]
    )
    for account in account_map.values():
        if account.type != AccountType.expense:
            raise FinClawError(
                "Budget lines must reference expense accounts",
                code="budget_account_not_expense",
            )

    existing_lines = (
        await db.execute(select(BudgetLine).where(BudgetLine.budget_id == budget.id))
    ).scalars().all()
    for existing in existing_lines:
        await db.delete(existing)
    await db.flush()

    for line in lines:
        db.add(
            BudgetLine(
                budget_id=budget.id,
                account_id=line.account_id,
                planned_amount=to_money(line.planned_amount),
                notes=line.notes,
            )
        )
    await db.flush()
    await db.refresh(budget, attribute_names=["lines"])


async def create_budget(db: AsyncSession, *, entity_id: uuid.UUID, payload: BudgetCreate) -> Budget:
    await _get_personal_entity(db, entity_id)
    if payload.period_end < payload.period_start:
        raise FinClawError("period_end must be on or after period_start", code="invalid_budget_period")
    budget = Budget(
        entity_id=entity_id,
        name=payload.name,
        period_start=payload.period_start,
        period_end=payload.period_end,
        notes=payload.notes,
    )
    db.add(budget)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("Budget already exists for this period", code="duplicate_budget") from exc
    await _replace_budget_lines(db, budget, payload.lines)
    return budget


async def update_budget(db: AsyncSession, budget: Budget, *, payload: BudgetUpdate) -> Budget:
    if payload.name is not None:
        budget.name = payload.name
    if payload.period_start is not None:
        budget.period_start = payload.period_start
    if payload.period_end is not None:
        budget.period_end = payload.period_end
    if budget.period_end < budget.period_start:
        raise FinClawError("period_end must be on or after period_start", code="invalid_budget_period")
    if payload.notes is not None:
        budget.notes = payload.notes
    if payload.lines is not None:
        await _replace_budget_lines(db, budget, payload.lines)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("Budget already exists for this period", code="duplicate_budget") from exc
    return budget


async def delete_budget(db: AsyncSession, budget: Budget) -> None:
    await db.delete(budget)
    await db.flush()


async def list_goals(db: AsyncSession, *, entity_id: uuid.UUID) -> list[Goal]:
    await _get_personal_entity(db, entity_id)
    rows = (
        await db.execute(select(Goal).where(Goal.entity_id == entity_id).order_by(Goal.created_at.desc()))
    ).scalars()
    return list(rows)


async def get_goal(db: AsyncSession, *, entity_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
    await _get_personal_entity(db, entity_id)
    goal = (
        await db.execute(select(Goal).where(Goal.id == goal_id, Goal.entity_id == entity_id))
    ).scalar_one_or_none()
    if goal is None:
        raise NotFoundError(f"Goal {goal_id} not found", code="goal_not_found")
    return goal


async def create_goal(db: AsyncSession, *, entity_id: uuid.UUID, payload: GoalCreate) -> Goal:
    await _get_personal_entity(db, entity_id)
    if payload.linked_account_id is not None:
        await _get_account_map(db, entity_id, [payload.linked_account_id])
    goal = Goal(
        entity_id=entity_id,
        name=payload.name,
        kind=payload.kind,
        target_amount=to_money(payload.target_amount),
        target_date=payload.target_date,
        current_amount=to_money(payload.current_amount),
        linked_account_id=payload.linked_account_id,
        status=payload.status,
        notes=payload.notes,
    )
    db.add(goal)
    await db.flush()
    return goal


async def update_goal(db: AsyncSession, goal: Goal, *, payload: GoalUpdate) -> Goal:
    if payload.name is not None:
        goal.name = payload.name
    if payload.kind is not None:
        goal.kind = payload.kind
    if payload.target_amount is not None:
        goal.target_amount = to_money(payload.target_amount)
    if payload.target_date is not None:
        goal.target_date = payload.target_date
    if payload.current_amount is not None:
        goal.current_amount = to_money(payload.current_amount)
    if payload.linked_account_id is not None:
        await _get_account_map(db, goal.entity_id, [payload.linked_account_id])
        goal.linked_account_id = payload.linked_account_id
    if payload.status is not None:
        goal.status = payload.status
    if payload.notes is not None:
        goal.notes = payload.notes
    await db.flush()
    return goal


async def delete_goal(db: AsyncSession, goal: Goal) -> None:
    await db.delete(goal)
    await db.flush()


async def list_debts(db: AsyncSession, *, entity_id: uuid.UUID) -> list[Debt]:
    await _get_personal_entity(db, entity_id)
    rows = (
        await db.execute(select(Debt).where(Debt.entity_id == entity_id).order_by(Debt.created_at.desc()))
    ).scalars()
    return list(rows)


async def get_debt(db: AsyncSession, *, entity_id: uuid.UUID, debt_id: uuid.UUID) -> Debt:
    await _get_personal_entity(db, entity_id)
    debt = (
        await db.execute(select(Debt).where(Debt.id == debt_id, Debt.entity_id == entity_id))
    ).scalar_one_or_none()
    if debt is None:
        raise NotFoundError(f"Debt {debt_id} not found", code="debt_not_found")
    return debt


async def create_debt(db: AsyncSession, *, entity_id: uuid.UUID, payload: DebtCreate) -> Debt:
    await _get_personal_entity(db, entity_id)
    if not payload.confirmed:
        raise FinClawError(
            "Debt creation requires explicit confirmation",
            code="confirmation_required",
        )
    if payload.linked_account_id is not None:
        account = (await _get_account_map(db, entity_id, [payload.linked_account_id]))[payload.linked_account_id]
        if account.type != AccountType.liability:
            raise FinClawError("Debt must link to a liability account", code="debt_account_not_liability")
    debt = Debt(
        entity_id=entity_id,
        name=payload.name,
        kind=payload.kind,
        original_principal=to_money(payload.original_principal) if payload.original_principal is not None else None,
        current_balance=to_money(payload.current_balance),
        interest_rate_apr=payload.interest_rate_apr,
        minimum_payment=to_money(payload.minimum_payment) if payload.minimum_payment is not None else None,
        due_day_of_month=payload.due_day_of_month,
        next_due_date=payload.next_due_date,
        linked_account_id=payload.linked_account_id,
        status=payload.status,
        notes=payload.notes,
    )
    db.add(debt)
    await db.flush()
    return debt


async def update_debt(db: AsyncSession, debt: Debt, *, payload: DebtUpdate) -> Debt:
    if payload.name is not None:
        debt.name = payload.name
    if payload.kind is not None:
        debt.kind = payload.kind
    if payload.original_principal is not None:
        debt.original_principal = to_money(payload.original_principal)
    if payload.current_balance is not None:
        debt.current_balance = to_money(payload.current_balance)
    if payload.interest_rate_apr is not None:
        debt.interest_rate_apr = payload.interest_rate_apr
    if payload.minimum_payment is not None:
        debt.minimum_payment = to_money(payload.minimum_payment)
    if payload.due_day_of_month is not None:
        debt.due_day_of_month = payload.due_day_of_month
    if payload.next_due_date is not None:
        debt.next_due_date = payload.next_due_date
    if payload.linked_account_id is not None:
        account = (await _get_account_map(db, debt.entity_id, [payload.linked_account_id]))[payload.linked_account_id]
        if account.type != AccountType.liability:
            raise FinClawError("Debt must link to a liability account", code="debt_account_not_liability")
        debt.linked_account_id = payload.linked_account_id
    if payload.status is not None:
        debt.status = payload.status
    if payload.notes is not None:
        debt.notes = payload.notes
    await db.flush()
    return debt


async def delete_debt(db: AsyncSession, debt: Debt) -> None:
    await db.delete(debt)
    await db.flush()


async def list_investment_accounts(db: AsyncSession, *, entity_id: uuid.UUID) -> list[InvestmentAccount]:
    await _get_personal_entity(db, entity_id)
    rows = (
        await db.execute(
            select(InvestmentAccount)
            .options(selectinload(InvestmentAccount.holdings))
            .where(InvestmentAccount.entity_id == entity_id)
            .order_by(InvestmentAccount.created_at.desc())
        )
    ).scalars()
    return list(rows)


async def get_investment_account(
    db: AsyncSession, *, entity_id: uuid.UUID, investment_account_id: uuid.UUID
) -> InvestmentAccount:
    await _get_personal_entity(db, entity_id)
    account = (
        await db.execute(
            select(InvestmentAccount)
            .options(selectinload(InvestmentAccount.holdings))
            .where(
                InvestmentAccount.id == investment_account_id,
                InvestmentAccount.entity_id == entity_id,
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise NotFoundError(
            f"Investment account {investment_account_id} not found",
            code="investment_account_not_found",
        )
    return account


async def _replace_holdings(
    db: AsyncSession,
    investment_account: InvestmentAccount,
    holdings: list[InvestmentHoldingIn],
) -> None:
    existing_holdings = (
        await db.execute(
            select(InvestmentHolding).where(
                InvestmentHolding.investment_account_id == investment_account.id
            )
        )
    ).scalars().all()
    for existing in existing_holdings:
        await db.delete(existing)
    await db.flush()
    for holding in holdings:
        db.add(
            InvestmentHolding(
                investment_account_id=investment_account.id,
                symbol=holding.symbol.upper(),
                name=holding.name,
                kind=holding.kind,
                shares=holding.shares,
                cost_basis_per_share=holding.cost_basis_per_share,
                current_price=holding.current_price,
                last_priced_at=holding.last_priced_at,
            )
        )
    await db.flush()
    await db.refresh(investment_account, attribute_names=["holdings"])


async def create_investment_account(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    payload: InvestmentAccountCreate,
) -> InvestmentAccount:
    await _get_personal_entity(db, entity_id)
    if not payload.confirmed:
        raise FinClawError(
            "Investment account creation requires explicit confirmation",
            code="confirmation_required",
        )
    if payload.linked_account_id is not None:
        account = (await _get_account_map(db, entity_id, [payload.linked_account_id]))[payload.linked_account_id]
        if account.type != AccountType.asset:
            raise FinClawError(
                "Investment accounts must link to asset accounts",
                code="investment_account_not_asset",
            )
    investment_account = InvestmentAccount(
        entity_id=entity_id,
        name=payload.name,
        broker=payload.broker,
        kind=payload.kind,
        currency=payload.currency.upper(),
        linked_account_id=payload.linked_account_id,
        notes=payload.notes,
    )
    db.add(investment_account)
    await db.flush()
    await _replace_holdings(db, investment_account, payload.holdings)
    return investment_account


async def update_investment_account(
    db: AsyncSession,
    investment_account: InvestmentAccount,
    *,
    payload: InvestmentAccountUpdate,
) -> InvestmentAccount:
    if payload.name is not None:
        investment_account.name = payload.name
    if payload.broker is not None:
        investment_account.broker = payload.broker
    if payload.kind is not None:
        investment_account.kind = payload.kind
    if payload.currency is not None:
        investment_account.currency = payload.currency.upper()
    if payload.linked_account_id is not None:
        account = (await _get_account_map(db, investment_account.entity_id, [payload.linked_account_id]))[payload.linked_account_id]
        if account.type != AccountType.asset:
            raise FinClawError(
                "Investment accounts must link to asset accounts",
                code="investment_account_not_asset",
            )
        investment_account.linked_account_id = payload.linked_account_id
    if payload.notes is not None:
        investment_account.notes = payload.notes
    if payload.holdings is not None:
        await _replace_holdings(db, investment_account, payload.holdings)
    await db.flush()
    return investment_account


async def delete_investment_account(db: AsyncSession, investment_account: InvestmentAccount) -> None:
    await db.delete(investment_account)
    await db.flush()


async def personal_dashboard(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID,
    as_of: date,
) -> PersonalDashboardOut:
    await _get_personal_entity(db, entity_id)
    month_start, month_end = _month_bounds(as_of)
    cumulative_balances = await _account_balances(db, entity_id=entity_id, date_to=as_of)
    monthly_balances = await _account_balances(
        db,
        entity_id=entity_id,
        date_from=month_start,
        date_to=min(month_end, as_of),
    )

    net_worth = ZERO
    emergency_fund_balance = ZERO
    monthly_income = ZERO
    monthly_expenses = ZERO

    for row in cumulative_balances.values():
        balance = row["balance"]
        if row["type"] == AccountType.asset:
            net_worth += balance
            if row["code"] == "1130":
                emergency_fund_balance = balance
        elif row["type"] == AccountType.liability:
            net_worth -= balance

    for row in monthly_balances.values():
        balance = row["balance"]
        if row["type"] == AccountType.income:
            monthly_income += balance
        elif row["type"] == AccountType.expense:
            monthly_expenses += balance

    monthly_income = to_money(monthly_income)
    monthly_expenses = to_money(monthly_expenses)
    net_worth = to_money(net_worth)
    emergency_fund_balance = to_money(emergency_fund_balance)
    monthly_savings = to_money(monthly_income - monthly_expenses)
    savings_rate = ZERO if monthly_income == ZERO else to_money(monthly_savings / monthly_income)
    emergency_fund_months = ZERO if monthly_expenses == ZERO else to_money(emergency_fund_balance / monthly_expenses)

    debts = (
        await db.execute(select(Debt).where(Debt.entity_id == entity_id, Debt.status == "active"))
    ).scalars().all()
    total_debt = ZERO
    for debt in debts:
        if debt.linked_account_id and debt.linked_account_id in cumulative_balances:
            total_debt += cumulative_balances[debt.linked_account_id]["balance"]
        else:
            total_debt += to_money(debt.current_balance)
    total_debt = to_money(total_debt)
    debt_to_income_ratio = ZERO if monthly_income == ZERO else to_money(total_debt / monthly_income)

    investment_accounts = (
        await db.execute(
            select(InvestmentAccount)
            .options(selectinload(InvestmentAccount.holdings))
            .where(InvestmentAccount.entity_id == entity_id)
        )
    ).scalars().all()
    allocations = defaultdict(lambda: ZERO)
    investment_value = ZERO
    for account in investment_accounts:
        for holding in account.holdings:
            price = holding.current_price
            if price is None:
                price = holding.cost_basis_per_share
            if price is None:
                holding_value = ZERO
            else:
                holding_value = to_money(holding.shares * price)
            allocations[holding.kind.value] += holding_value
            investment_value += holding_value
    investment_value = to_money(investment_value)
    allocation_rows: list[InvestmentAllocationRow] = []
    for label, value in sorted(allocations.items()):
        ratio = ZERO if investment_value == ZERO else to_money(value / investment_value)
        allocation_rows.append(
            InvestmentAllocationRow(label=label, value=to_money(value), allocation_ratio=ratio)
        )

    goals = (
        await db.execute(select(Goal).where(Goal.entity_id == entity_id, Goal.status == "active"))
    ).scalars().all()
    goal_progress: list[GoalProgressOut] = []
    for goal in goals:
        current = (
            cumulative_balances.get(goal.linked_account_id, {}).get("balance", ZERO)
            if goal.linked_account_id
            else to_money(goal.current_amount)
        )
        ratio = ZERO if goal.target_amount == ZERO else to_money(current / goal.target_amount)
        goal_progress.append(
            GoalProgressOut(
                goal_id=goal.id,
                name=goal.name,
                kind=goal.kind,
                target_amount=to_money(goal.target_amount),
                current_amount=to_money(current),
                progress_ratio=ratio,
            )
        )

    return PersonalDashboardOut(
        entity_id=entity_id,
        as_of=as_of,
        month_start=month_start,
        month_end=month_end,
        net_worth=net_worth,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        monthly_savings=monthly_savings,
        savings_rate=savings_rate,
        emergency_fund_balance=emergency_fund_balance,
        emergency_fund_months=emergency_fund_months,
        total_debt=total_debt,
        debt_to_income_ratio=debt_to_income_ratio,
        investment_value=investment_value,
        investment_allocation=allocation_rows,
        goal_progress=goal_progress,
        investment_disclaimer=INVESTMENT_DISCLAIMER,
    )
