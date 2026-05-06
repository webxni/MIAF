from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from starlette.responses import StreamingResponse

from app.api.deps import DB, CurrentUserDep, RequestCtx, require_reader, require_writer
from app.models import Entity, EntityMember
from app.schemas.personal import (
    BudgetActualsOut,
    BudgetCreate,
    BudgetOut,
    BudgetUpdate,
    BusinessDependencyOut,
    CashFlowSummaryOut,
    DebtCreate,
    DebtPayoffPlanOut,
    DebtOut,
    DebtUpdate,
    EmergencyFundPlanOut,
    ExplanationOut,
    GoalCreate,
    GoalOut,
    GoalUpdate,
    InvestmentAccountCreate,
    InvestmentAccountOut,
    InvestmentAccountUpdate,
    InvestmentAllocationSummaryOut,
    NetWorthSnapshotOut,
    PersonalDashboardOut,
)
from app.services.audit import write_audit
from app.services.personal import (
    budget_actuals,
    create_net_worth_snapshot,
    create_budget,
    create_debt,
    create_goal,
    create_investment_account,
    delete_budget,
    delete_debt,
    delete_goal,
    debt_payoff_plan,
    emergency_fund_plan,
    explain_net_worth_change,
    explain_spending_trends,
    delete_investment_account,
    get_budget,
    get_debt,
    get_goal,
    get_investment_account,
    investment_allocation_summary,
    list_budgets,
    list_debts,
    list_goals,
    list_investment_accounts,
    list_net_worth_snapshots,
    monthly_cash_flow_report,
    net_worth_statement,
    personal_dashboard,
    update_budget,
    update_debt,
    update_goal,
    update_investment_account,
)

router = APIRouter(prefix="/entities/{entity_id}/personal", tags=["personal"])


def _make_csv(headers: list[str], rows: list[list]) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment"},
    )


def _budget_dict(budget) -> dict:
    return {
        "id": str(budget.id),
        "name": budget.name,
        "period_start": budget.period_start.isoformat(),
        "period_end": budget.period_end.isoformat(),
        "notes": budget.notes,
        "lines": [
            {
                "account_id": str(line.account_id),
                "planned_amount": str(line.planned_amount),
                "notes": line.notes,
            }
            for line in budget.lines
        ],
    }


def _goal_dict(goal) -> dict:
    return {
        "id": str(goal.id),
        "name": goal.name,
        "kind": goal.kind.value,
        "target_amount": str(goal.target_amount),
        "current_amount": str(goal.current_amount),
        "linked_account_id": str(goal.linked_account_id) if goal.linked_account_id else None,
        "status": goal.status.value,
    }


def _debt_dict(debt) -> dict:
    return {
        "id": str(debt.id),
        "name": debt.name,
        "kind": debt.kind.value,
        "current_balance": str(debt.current_balance),
        "linked_account_id": str(debt.linked_account_id) if debt.linked_account_id else None,
        "status": debt.status.value,
    }


def _investment_account_dict(account) -> dict:
    return {
        "id": str(account.id),
        "name": account.name,
        "kind": account.kind.value,
        "linked_account_id": str(account.linked_account_id) if account.linked_account_id else None,
        "holdings": [
            {
                "symbol": holding.symbol,
                "kind": holding.kind.value,
                "shares": str(holding.shares),
                "current_price": str(holding.current_price) if holding.current_price is not None else None,
            }
            for holding in account.holdings
        ],
    }


@router.get("/dashboard", response_model=PersonalDashboardOut)
async def dashboard_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> PersonalDashboardOut:
    return await personal_dashboard(db, entity_id=entity_id, as_of=as_of)


@router.get("/reports/net-worth", response_model=NetWorthSnapshotOut)
async def net_worth_report_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> NetWorthSnapshotOut:
    result = await net_worth_statement(db, entity_id=entity_id, as_of=as_of)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="report_viewed", object_type="net_worth", object_id=None, after={"as_of": str(as_of)}, ip=ctx.ip, user_agent=ctx.user_agent)
    return result


@router.get("/reports/net-worth/export.csv")
async def net_worth_csv(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> StreamingResponse:
    result = await net_worth_statement(db, entity_id=entity_id, as_of=as_of)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="export", object_type="net_worth", object_id=None, after={"format": "csv", "as_of": str(as_of)}, ip=ctx.ip, user_agent=ctx.user_agent)
    headers = ["Metric", "Amount"]
    rows = [
        ["Total Assets", str(result.total_assets)],
        ["Total Liabilities", str(result.total_liabilities)],
        ["Net Worth", str(result.net_worth)],
        ["As Of", str(result.as_of)],
    ]
    return _make_csv(headers, rows)


@router.get("/reports/monthly-cash-flow", response_model=CashFlowSummaryOut)
async def monthly_cash_flow_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> CashFlowSummaryOut:
    result = await monthly_cash_flow_report(db, entity_id=entity_id, as_of=as_of)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="report_viewed", object_type="monthly_cash_flow", object_id=None, after={"as_of": str(as_of)}, ip=ctx.ip, user_agent=ctx.user_agent)
    return result


@router.get("/reports/debt-payoff-plan", response_model=DebtPayoffPlanOut)
async def debt_payoff_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> DebtPayoffPlanOut:
    result = await debt_payoff_plan(db, entity_id=entity_id, as_of=as_of)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="report_viewed", object_type="debt_payoff_plan", object_id=None, after={"as_of": str(as_of)}, ip=ctx.ip, user_agent=ctx.user_agent)
    return result


@router.get("/reports/emergency-fund-plan", response_model=EmergencyFundPlanOut)
async def emergency_fund_plan_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> EmergencyFundPlanOut:
    result = await emergency_fund_plan(db, entity_id=entity_id, as_of=as_of)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="report_viewed", object_type="emergency_fund_plan", object_id=None, after={"as_of": str(as_of)}, ip=ctx.ip, user_agent=ctx.user_agent)
    return result


@router.get("/reports/investment-allocation", response_model=InvestmentAllocationSummaryOut)
async def investment_allocation_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> InvestmentAllocationSummaryOut:
    result = await investment_allocation_summary(db, entity_id=entity_id, as_of=as_of)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="report_viewed", object_type="investment_allocation", object_id=None, after={"as_of": str(as_of)}, ip=ctx.ip, user_agent=ctx.user_agent)
    return result


@router.get("/reports/business-dependency", response_model=BusinessDependencyOut)
async def business_dependency_report_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> BusinessDependencyOut:
    dashboard = await personal_dashboard(db, entity_id=entity_id, as_of=as_of)
    await write_audit(db, tenant_id=me.tenant_id, user_id=me.id, entity_id=entity_id, action="report_viewed", object_type="business_dependency", object_id=None, after={"as_of": str(as_of)}, ip=ctx.ip, user_agent=ctx.user_agent)
    return dashboard.business_dependency


@router.get("/reports/net-worth-change-explanation", response_model=ExplanationOut)
async def net_worth_change_explanation_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    date_from: date,
    date_to: date,
) -> ExplanationOut:
    return await explain_net_worth_change(db, entity_id=entity_id, date_from=date_from, date_to=date_to)


@router.get("/reports/spending-trends-explanation", response_model=ExplanationOut)
async def spending_trends_explanation_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    as_of: date = Query(default_factory=date.today),
) -> ExplanationOut:
    return await explain_spending_trends(db, entity_id=entity_id, as_of=as_of)


@router.get("/budgets", response_model=list[BudgetOut])
async def list_budgets_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
) -> list[BudgetOut]:
    return [BudgetOut.model_validate(item) for item in await list_budgets(db, entity_id=entity_id)]


@router.post("/budgets", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
async def create_budget_endpoint(
    entity_id: uuid.UUID,
    payload: BudgetCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> BudgetOut:
    budget = await create_budget(db, entity_id=entity_id, payload=payload)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="create",
        object_type="budget",
        object_id=budget.id,
        after=_budget_dict(budget),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return BudgetOut.model_validate(budget)


@router.get("/budgets/{budget_id}/actuals", response_model=BudgetActualsOut)
async def budget_actuals_endpoint(
    entity_id: uuid.UUID,
    budget_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
) -> BudgetActualsOut:
    return await budget_actuals(db, entity_id=entity_id, budget_id=budget_id)


@router.patch("/budgets/{budget_id}", response_model=BudgetOut)
async def update_budget_endpoint(
    entity_id: uuid.UUID,
    budget_id: uuid.UUID,
    payload: BudgetUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> BudgetOut:
    budget = await get_budget(db, entity_id=entity_id, budget_id=budget_id)
    before = _budget_dict(budget)
    budget = await update_budget(db, budget, payload=payload)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="update",
        object_type="budget",
        object_id=budget.id,
        before=before,
        after=_budget_dict(budget),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return BudgetOut.model_validate(budget)


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_budget_endpoint(
    entity_id: uuid.UUID,
    budget_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> Response:
    budget = await get_budget(db, entity_id=entity_id, budget_id=budget_id)
    before = _budget_dict(budget)
    await delete_budget(db, budget)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="delete",
        object_type="budget",
        object_id=budget_id,
        before=before,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/goals", response_model=list[GoalOut])
async def list_goals_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
) -> list[GoalOut]:
    return [GoalOut.model_validate(item) for item in await list_goals(db, entity_id=entity_id)]


@router.post("/goals", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
async def create_goal_endpoint(
    entity_id: uuid.UUID,
    payload: GoalCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> GoalOut:
    goal = await create_goal(db, entity_id=entity_id, payload=payload)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="create",
        object_type="goal",
        object_id=goal.id,
        after=_goal_dict(goal),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return GoalOut.model_validate(goal)


@router.patch("/goals/{goal_id}", response_model=GoalOut)
async def update_goal_endpoint(
    entity_id: uuid.UUID,
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> GoalOut:
    goal = await get_goal(db, entity_id=entity_id, goal_id=goal_id)
    before = _goal_dict(goal)
    goal = await update_goal(db, goal, payload=payload)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="update",
        object_type="goal",
        object_id=goal.id,
        before=before,
        after=_goal_dict(goal),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return GoalOut.model_validate(goal)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_goal_endpoint(
    entity_id: uuid.UUID,
    goal_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> Response:
    goal = await get_goal(db, entity_id=entity_id, goal_id=goal_id)
    before = _goal_dict(goal)
    await delete_goal(db, goal)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="delete",
        object_type="goal",
        object_id=goal_id,
        before=before,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/debts", response_model=list[DebtOut])
async def list_debts_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
) -> list[DebtOut]:
    return [DebtOut.model_validate(item) for item in await list_debts(db, entity_id=entity_id)]


@router.post("/debts", response_model=DebtOut, status_code=status.HTTP_201_CREATED)
async def create_debt_endpoint(
    entity_id: uuid.UUID,
    payload: DebtCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> DebtOut:
    debt = await create_debt(db, entity_id=entity_id, payload=payload)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="create",
        object_type="debt",
        object_id=debt.id,
        after=_debt_dict(debt),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return DebtOut.model_validate(debt)


@router.patch("/debts/{debt_id}", response_model=DebtOut)
async def update_debt_endpoint(
    entity_id: uuid.UUID,
    debt_id: uuid.UUID,
    payload: DebtUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> DebtOut:
    debt = await get_debt(db, entity_id=entity_id, debt_id=debt_id)
    before = _debt_dict(debt)
    debt = await update_debt(db, debt, payload=payload)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="update",
        object_type="debt",
        object_id=debt.id,
        before=before,
        after=_debt_dict(debt),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return DebtOut.model_validate(debt)


@router.delete("/debts/{debt_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_debt_endpoint(
    entity_id: uuid.UUID,
    debt_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> Response:
    debt = await get_debt(db, entity_id=entity_id, debt_id=debt_id)
    before = _debt_dict(debt)
    await delete_debt(db, debt)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="delete",
        object_type="debt",
        object_id=debt_id,
        before=before,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/investments", response_model=list[InvestmentAccountOut])
async def list_investments_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
) -> list[InvestmentAccountOut]:
    return [
        InvestmentAccountOut.model_validate(item)
        for item in await list_investment_accounts(db, entity_id=entity_id)
    ]


@router.post("/investments", response_model=InvestmentAccountOut, status_code=status.HTTP_201_CREATED)
async def create_investment_endpoint(
    entity_id: uuid.UUID,
    payload: InvestmentAccountCreate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> InvestmentAccountOut:
    investment_account = await create_investment_account(db, entity_id=entity_id, payload=payload)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="create",
        object_type="investment_account",
        object_id=investment_account.id,
        after=_investment_account_dict(investment_account),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return InvestmentAccountOut.model_validate(investment_account)


@router.patch("/investments/{investment_account_id}", response_model=InvestmentAccountOut)
async def update_investment_endpoint(
    entity_id: uuid.UUID,
    investment_account_id: uuid.UUID,
    payload: InvestmentAccountUpdate,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> InvestmentAccountOut:
    investment_account = await get_investment_account(
        db, entity_id=entity_id, investment_account_id=investment_account_id
    )
    before = _investment_account_dict(investment_account)
    investment_account = await update_investment_account(db, investment_account, payload=payload)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="update",
        object_type="investment_account",
        object_id=investment_account.id,
        before=before,
        after=_investment_account_dict(investment_account),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return InvestmentAccountOut.model_validate(investment_account)


@router.delete(
    "/investments/{investment_account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_investment_endpoint(
    entity_id: uuid.UUID,
    investment_account_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
) -> Response:
    investment_account = await get_investment_account(
        db, entity_id=entity_id, investment_account_id=investment_account_id
    )
    before = _investment_account_dict(investment_account)
    await delete_investment_account(db, investment_account)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="delete",
        object_type="investment_account",
        object_id=investment_account_id,
        before=before,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/net-worth-snapshots", response_model=NetWorthSnapshotOut, status_code=status.HTTP_201_CREATED)
async def create_net_worth_snapshot_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    me: CurrentUserDep,
    ctx: RequestCtx,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_writer)],
    as_of: date = Query(default_factory=date.today),
) -> NetWorthSnapshotOut:
    snapshot = await create_net_worth_snapshot(db, entity_id=entity_id, as_of=as_of)
    await write_audit(
        db,
        tenant_id=me.tenant_id,
        user_id=me.id,
        entity_id=entity_id,
        action="create",
        object_type="net_worth_snapshot",
        object_id=snapshot.id,
        after={
            "as_of": snapshot.as_of.isoformat(),
            "total_assets": str(snapshot.total_assets),
            "total_liabilities": str(snapshot.total_liabilities),
            "net_worth": str(snapshot.net_worth),
        },
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    return NetWorthSnapshotOut.model_validate(snapshot)


@router.get("/net-worth-snapshots", response_model=list[NetWorthSnapshotOut])
async def list_net_worth_snapshots_endpoint(
    entity_id: uuid.UUID,
    db: DB,
    scoped: Annotated[tuple[Entity, EntityMember], Depends(require_reader)],
    limit: int = Query(default=12, ge=1, le=120),
) -> list[NetWorthSnapshotOut]:
    rows = await list_net_worth_snapshots(db, entity_id=entity_id, limit=limit)
    return [NetWorthSnapshotOut.model_validate(row) for row in rows]
