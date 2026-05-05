from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import FinClawError
from app.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Bill,
    BusinessDocumentStatus,
    DebtStatus,
    Entity,
    EntityMode,
    GeneratedReport,
    HeartbeatRun,
    HeartbeatRunStatus,
    HeartbeatType,
    Invoice,
    ReportKind,
    TaxReserve,
    Tenant,
)
from app.models.base import utcnow
from app.services.audit import write_audit
from app.services.business import ap_aging, ar_aging, business_dashboard, list_tax_reserves
from app.services.personal import budget_actuals, list_budgets, list_debts, personal_dashboard


@dataclass
class HeartbeatResult:
    run: HeartbeatRun
    alerts: list[Alert]
    reports: list[GeneratedReport]


async def list_runs(db: AsyncSession, *, tenant_id: uuid.UUID, limit: int = 20) -> list[HeartbeatRun]:
    return list(
        (
            await db.execute(
                select(HeartbeatRun)
                .where(HeartbeatRun.tenant_id == tenant_id)
                .order_by(HeartbeatRun.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    )


async def list_alerts(db: AsyncSession, *, tenant_id: uuid.UUID, only_open: bool = True, limit: int = 50) -> list[Alert]:
    stmt = select(Alert).where(Alert.tenant_id == tenant_id)
    if only_open:
        stmt = stmt.where(Alert.status == AlertStatus.open)
    stmt = stmt.order_by(Alert.created_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def list_reports(db: AsyncSession, *, tenant_id: uuid.UUID, limit: int = 20) -> list[GeneratedReport]:
    stmt = (
        select(GeneratedReport)
        .where(GeneratedReport.tenant_id == tenant_id)
        .order_by(GeneratedReport.created_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def run_heartbeat(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    heartbeat_type: HeartbeatType,
    as_of: date,
    trigger_source: str,
    initiated_by_user_id: uuid.UUID | None,
) -> HeartbeatResult:
    run = HeartbeatRun(
        tenant_id=tenant_id,
        heartbeat_type=heartbeat_type,
        status=HeartbeatRunStatus.running,
        trigger_source=trigger_source,
        started_at=utcnow(),
        initiated_by_user_id=initiated_by_user_id,
    )
    db.add(run)
    await db.flush()

    alerts: list[Alert] = []
    reports: list[GeneratedReport] = []
    entities = list(
        (
            await db.execute(
                select(Entity).where(Entity.tenant_id == tenant_id).order_by(Entity.created_at)
            )
        ).scalars().all()
    )

    try:
        for entity in entities:
            if heartbeat_type == HeartbeatType.daily_personal_check and entity.mode == EntityMode.personal:
                alerts.extend(await _daily_personal_check(db, run=run, entity=entity, as_of=as_of))
            elif heartbeat_type == HeartbeatType.daily_business_check and entity.mode == EntityMode.business:
                alerts.extend(await _daily_business_check(db, run=run, entity=entity, as_of=as_of))
            elif heartbeat_type == HeartbeatType.weekly_business_report and entity.mode == EntityMode.business:
                reports.append(await _weekly_business_report(db, run=run, entity=entity, as_of=as_of))
            else:
                continue

        run.status = HeartbeatRunStatus.completed
        run.finished_at = utcnow()
        run.summary = {
            "entities_scanned": len(entities),
            "alerts_created": len(alerts),
            "reports_created": len(reports),
        }
    except Exception as exc:
        run.status = HeartbeatRunStatus.failed
        run.finished_at = utcnow()
        run.error_message = str(exc)
        await write_audit(
            db,
            tenant_id=tenant_id,
            user_id=initiated_by_user_id,
            entity_id=None,
            action="run",
            object_type="heartbeat",
            object_id=run.id,
            after={"status": run.status.value, "error_message": run.error_message},
        )
        raise

    await write_audit(
        db,
        tenant_id=tenant_id,
        user_id=initiated_by_user_id,
        entity_id=None,
        action="run",
        object_type="heartbeat",
        object_id=run.id,
        after={
            "heartbeat_type": heartbeat_type.value,
            "status": run.status.value,
            "trigger_source": trigger_source,
            **(run.summary or {}),
        },
    )
    await db.flush()
    return HeartbeatResult(run=run, alerts=alerts, reports=reports)


async def run_default_scheduled_heartbeats(db: AsyncSession, *, as_of: date) -> list[HeartbeatRun]:
    tenant_ids = list((await db.execute(select(Tenant.id))).scalars().all())
    runs: list[HeartbeatRun] = []
    for tenant_id in tenant_ids:
        runs.append(
            (
                await run_heartbeat(
                    db,
                    tenant_id=tenant_id,
                    heartbeat_type=HeartbeatType.daily_personal_check,
                    as_of=as_of,
                    trigger_source="scheduler",
                    initiated_by_user_id=None,
                )
            ).run
        )
        runs.append(
            (
                await run_heartbeat(
                    db,
                    tenant_id=tenant_id,
                    heartbeat_type=HeartbeatType.daily_business_check,
                    as_of=as_of,
                    trigger_source="scheduler",
                    initiated_by_user_id=None,
                )
            ).run
        )
        if as_of.weekday() == 0:
            runs.append(
                (
                    await run_heartbeat(
                        db,
                        tenant_id=tenant_id,
                        heartbeat_type=HeartbeatType.weekly_business_report,
                        as_of=as_of,
                        trigger_source="scheduler",
                        initiated_by_user_id=None,
                    )
                ).run
            )
    return runs


async def _create_alert(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity_id: uuid.UUID | None,
    alert_type: str,
    severity: AlertSeverity,
    title: str,
    message: str,
    payload: dict | None = None,
) -> Alert:
    row = Alert(
        tenant_id=run.tenant_id,
        entity_id=entity_id,
        heartbeat_run_id=run.id,
        alert_type=alert_type,
        severity=severity,
        status=AlertStatus.open,
        title=title,
        message=message,
        payload=payload,
    )
    db.add(row)
    await db.flush()
    return row


async def _daily_personal_check(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity: Entity,
    as_of: date,
) -> list[Alert]:
    alerts: list[Alert] = []
    dashboard = await personal_dashboard(db, entity_id=entity.id, as_of=as_of)

    if dashboard.emergency_fund_months < Decimal("1"):
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="emergency_fund_low",
                severity=AlertSeverity.critical,
                title="Emergency fund is below one month",
                message="Personal reserves are under one month of expenses.",
                payload={"emergency_fund_months": str(dashboard.emergency_fund_months)},
            )
        )
    elif dashboard.emergency_fund_months < Decimal("3"):
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="emergency_fund_thin",
                severity=AlertSeverity.warning,
                title="Emergency fund is below the preferred floor",
                message="Personal reserves are below three months of expenses.",
                payload={"emergency_fund_months": str(dashboard.emergency_fund_months)},
            )
        )

    for debt in await list_debts(db, entity_id=entity.id):
        if debt.status != DebtStatus.active or debt.next_due_date is None:
            continue
        if debt.next_due_date <= as_of + timedelta(days=7):
            alerts.append(
                await _create_alert(
                    db,
                    run=run,
                    entity_id=entity.id,
                    alert_type="debt_due_soon",
                    severity=AlertSeverity.warning,
                    title=f"Debt payment due soon: {debt.name}",
                    message=f"{debt.name} is due on {debt.next_due_date.isoformat()}.",
                    payload={"debt_id": str(debt.id), "due_date": debt.next_due_date.isoformat()},
                )
            )

    for budget in await list_budgets(db, entity_id=entity.id):
        if not (budget.period_start <= as_of <= budget.period_end):
            continue
        actuals = await budget_actuals(db, budget=budget)
        overspent = [line for line in actuals.lines if line.overspent]
        if overspent:
            alerts.append(
                await _create_alert(
                    db,
                    run=run,
                    entity_id=entity.id,
                    alert_type="budget_overspend",
                    severity=AlertSeverity.warning,
                    title=f"Budget overspend in {budget.name}",
                    message=f"{len(overspent)} budget categories are over plan.",
                    payload={"budget_id": str(budget.id), "overspent_accounts": [line.account_code for line in overspent]},
                )
            )
    return alerts


async def _daily_business_check(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity: Entity,
    as_of: date,
) -> list[Alert]:
    alerts: list[Alert] = []
    dashboard = await business_dashboard(db, entity_id=entity.id, as_of=as_of)
    runway = None
    if dashboard.monthly_expenses > Decimal("0"):
        runway = dashboard.cash_balance / dashboard.monthly_expenses
        if runway < Decimal("1"):
            alerts.append(
                await _create_alert(
                    db,
                    run=run,
                    entity_id=entity.id,
                    alert_type="cash_runway_low",
                    severity=AlertSeverity.critical,
                    title="Business cash runway is below one month",
                    message="Operating cash covers less than one month of current expenses.",
                    payload={"runway_months": str(round(runway, 2))},
                )
            )
        elif runway < Decimal("2"):
            alerts.append(
                await _create_alert(
                    db,
                    run=run,
                    entity_id=entity.id,
                    alert_type="cash_runway_thin",
                    severity=AlertSeverity.warning,
                    title="Business cash runway is below two months",
                    message="Operating cash covers less than two months of current expenses.",
                    payload={"runway_months": str(round(runway, 2))},
                )
            )

    ar = await ar_aging(db, entity_id=entity.id, as_of=as_of)
    overdue_ar = [row for row in ar.rows if row.days_1_30 + row.days_31_60 + row.days_61_90 + row.days_91_plus > Decimal("0")]
    if overdue_ar:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="overdue_invoices",
                severity=AlertSeverity.warning,
                title="Overdue invoices need attention",
                message=f"{len(overdue_ar)} invoice(s) are overdue.",
                payload={"count": len(overdue_ar), "total_balance_due": str(ar.total_balance_due)},
            )
        )

    ap = await ap_aging(db, entity_id=entity.id, as_of=as_of)
    overdue_ap = [row for row in ap.rows if row.days_1_30 + row.days_31_60 + row.days_61_90 + row.days_91_plus > Decimal("0")]
    if overdue_ap:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="overdue_bills",
                severity=AlertSeverity.warning,
                title="Overdue bills need attention",
                message=f"{len(overdue_ap)} bill(s) are overdue.",
                payload={"count": len(overdue_ap), "total_balance_due": str(ap.total_balance_due)},
            )
        )

    tax_reserves = await list_tax_reserves(db, entity_id=entity.id)
    if tax_reserves:
        latest = sorted(tax_reserves, key=lambda item: item.as_of, reverse=True)[0]
        if latest.estimated_tax > latest.reserved_amount:
            alerts.append(
                await _create_alert(
                    db,
                    run=run,
                    entity_id=entity.id,
                    alert_type="tax_reserve_gap",
                    severity=AlertSeverity.warning,
                    title="Tax reserve is below estimated need",
                    message="Reserved tax cash is below the latest estimate.",
                    payload={
                        "estimated_tax": str(latest.estimated_tax),
                        "reserved_amount": str(latest.reserved_amount),
                    },
                )
            )
    return alerts


async def _weekly_business_report(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity: Entity,
    as_of: date,
) -> GeneratedReport:
    period_end = as_of
    period_start = as_of - timedelta(days=6)
    dashboard = await business_dashboard(db, entity_id=entity.id, as_of=as_of)
    ar = await ar_aging(db, entity_id=entity.id, as_of=as_of)
    ap = await ap_aging(db, entity_id=entity.id, as_of=as_of)
    body = "\n".join(
        [
            f"# Weekly Business Report: {entity.name}",
            f"- Period: {period_start.isoformat()} to {period_end.isoformat()}",
            f"- Cash balance: {dashboard.cash_balance}",
            f"- Revenue this month: {dashboard.monthly_revenue}",
            f"- Expenses this month: {dashboard.monthly_expenses}",
            f"- Net income this month: {dashboard.monthly_net_income}",
            f"- Accounts receivable: {dashboard.accounts_receivable}",
            f"- Accounts payable: {dashboard.accounts_payable}",
            f"- Overdue AR rows: {len([row for row in ar.rows if row.days_1_30 + row.days_31_60 + row.days_61_90 + row.days_91_plus > Decimal('0')])}",
            f"- Overdue AP rows: {len([row for row in ap.rows if row.days_1_30 + row.days_31_60 + row.days_61_90 + row.days_91_plus > Decimal('0')])}",
        ]
    )
    report = GeneratedReport(
        tenant_id=run.tenant_id,
        entity_id=entity.id,
        heartbeat_run_id=run.id,
        report_kind=ReportKind.weekly_business_report,
        period_start=period_start,
        period_end=period_end,
        title=f"Weekly business report for {entity.name}",
        body=body,
    )
    db.add(report)
    await db.flush()
    return report
