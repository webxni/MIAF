from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import MIAFError, NotFoundError
from app.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Bill,
    BusinessDocumentStatus,
    DebtStatus,
    DocumentExtraction,
    Entity,
    EntityMode,
    ExtractionStatus,
    GeneratedReport,
    HeartbeatRun,
    HeartbeatRunStatus,
    HeartbeatType,
    Invoice,
    JournalEntry,
    JournalEntryStatus,
    NetWorthSnapshot,
    ReportKind,
    SourceTransaction,
    TaxReserve,
    Tenant,
)
from app.models.base import utcnow
from app.services.audit import write_audit
from app.services.business import (
    ap_aging,
    ar_aging,
    business_dashboard,
    closing_checklist,
    list_tax_reserves,
    runway_report,
    tax_reserve_report,
)
from app.services.personal import (
    budget_actuals,
    create_net_worth_snapshot,
    debt_payoff_plan,
    emergency_fund_plan,
    list_budgets,
    list_debts,
    personal_dashboard,
)


def _open_question_count(extracted_data: dict | None) -> int:
    if not isinstance(extracted_data, dict):
        return 0
    items = extracted_data.get("items")
    if not isinstance(items, list):
        return 0
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        for question in item.get("questions", []):
            if isinstance(question, dict) and question.get("status") != "answered":
                count += 1
    return count


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


async def update_alert_status(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    alert_id: uuid.UUID,
    status: AlertStatus,
    user_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
) -> Alert:
    alert = (
        await db.execute(
            select(Alert).where(
                Alert.id == alert_id,
                Alert.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if alert is None:
        raise NotFoundError(f"Alert {alert_id} not found", code="alert_not_found")

    if alert.status != AlertStatus.open or status not in {AlertStatus.resolved, AlertStatus.dismissed}:
        raise MIAFError("invalid_alert_transition", code="invalid_alert_transition")

    before = {
        "status": alert.status.value,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at is not None else None,
    }
    alert.status = status
    alert.resolved_at = utcnow() if status == AlertStatus.resolved else None

    if hasattr(Alert, "resolved_by_id"):
        setattr(alert, "resolved_by_id", user_id)
    if hasattr(Alert, "resolved_action"):
        setattr(alert, "resolved_action", status.value)

    after = {
        "status": alert.status.value,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at is not None else None,
    }
    if hasattr(Alert, "resolved_by_id"):
        value = getattr(alert, "resolved_by_id", None)
        after["resolved_by_id"] = str(value) if value is not None else None
    if hasattr(Alert, "resolved_action"):
        after["resolved_action"] = getattr(alert, "resolved_action", None)

    await write_audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=alert.entity_id,
        action="update",
        object_type="alert",
        object_id=alert_id,
        before=before,
        after=after,
        ip=ip,
        user_agent=user_agent,
    )
    await db.flush()
    return alert


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
            elif heartbeat_type == HeartbeatType.weekly_personal_report and entity.mode == EntityMode.personal:
                alerts.extend(await _weekly_personal_report(db, run=run, entity=entity, as_of=as_of))
            elif heartbeat_type == HeartbeatType.monthly_personal_close and entity.mode == EntityMode.personal:
                alerts.extend(await _monthly_personal_close(db, run=run, entity=entity, as_of=as_of))
            elif heartbeat_type == HeartbeatType.daily_business_check and entity.mode == EntityMode.business:
                alerts.extend(await _daily_business_check(db, run=run, entity=entity, as_of=as_of))
            elif heartbeat_type == HeartbeatType.weekly_business_report and entity.mode == EntityMode.business:
                reports.append(await _weekly_business_report(db, run=run, entity=entity, as_of=as_of))
            elif heartbeat_type == HeartbeatType.monthly_business_close and entity.mode == EntityMode.business:
                alerts.extend(await _monthly_business_close(db, run=run, entity=entity, as_of=as_of))
            elif heartbeat_type == HeartbeatType.tax_reserve_check and entity.mode == EntityMode.business:
                alerts.extend(await _tax_reserve_check(db, run=run, entity=entity, as_of=as_of))
            elif heartbeat_type == HeartbeatType.cash_runway_check and entity.mode == EntityMode.business:
                alerts.extend(await _cash_runway_check(db, run=run, entity=entity, as_of=as_of))
            elif heartbeat_type == HeartbeatType.budget_overspend_check and entity.mode == EntityMode.personal:
                alerts.extend(await _budget_overspend_check(db, run=run, entity=entity, as_of=as_of))
            elif heartbeat_type == HeartbeatType.ar_ap_aging_check and entity.mode == EntityMode.business:
                alerts.extend(await _ar_ap_aging_check(db, run=run, entity=entity, as_of=as_of))
            else:
                continue

        reports = list(
            (
                await db.execute(
                    select(GeneratedReport)
                    .where(GeneratedReport.heartbeat_run_id == run.id)
                    .order_by(GeneratedReport.created_at)
                )
            ).scalars().all()
        )
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
        runs.append(
            (
                await run_heartbeat(
                    db,
                    tenant_id=tenant_id,
                    heartbeat_type=HeartbeatType.tax_reserve_check,
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
                    heartbeat_type=HeartbeatType.cash_runway_check,
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
                    heartbeat_type=HeartbeatType.budget_overspend_check,
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
            runs.append(
                (
                    await run_heartbeat(
                        db,
                        tenant_id=tenant_id,
                        heartbeat_type=HeartbeatType.ar_ap_aging_check,
                        as_of=as_of,
                        trigger_source="scheduler",
                        initiated_by_user_id=None,
                    )
                ).run
            )
        if as_of.weekday() == 6:
            runs.append(
                (
                    await run_heartbeat(
                        db,
                        tenant_id=tenant_id,
                        heartbeat_type=HeartbeatType.weekly_personal_report,
                        as_of=as_of,
                        trigger_source="scheduler",
                        initiated_by_user_id=None,
                    )
                ).run
            )
        if as_of.day == 1:
            runs.append(
                (
                    await run_heartbeat(
                        db,
                        tenant_id=tenant_id,
                        heartbeat_type=HeartbeatType.monthly_personal_close,
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
                        heartbeat_type=HeartbeatType.monthly_business_close,
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
    # Deduplicate: skip if an open alert of the same type already exists for this entity.
    dup_stmt = select(Alert).where(
        Alert.tenant_id == run.tenant_id,
        Alert.entity_id == entity_id,
        Alert.alert_type == alert_type,
        Alert.status == AlertStatus.open,
    ).limit(1)
    existing = (await db.execute(dup_stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

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


async def _document_review_alerts(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity: Entity,
) -> list[Alert]:
    alerts: list[Alert] = []
    extractions = list(
        (
            await db.execute(
                select(DocumentExtraction)
                .where(DocumentExtraction.entity_id == entity.id)
                .order_by(DocumentExtraction.created_at.desc())
                .limit(200)
            )
        ).scalars().all()
    )
    needs_review = [row for row in extractions if row.status in {ExtractionStatus.pending, ExtractionStatus.needs_review}]
    duplicate_count = sum(1 for row in extractions if row.duplicate_detected)
    low_confidence = [
        row for row in extractions if row.confidence_score is not None and row.confidence_score < Decimal("0.5500")
    ]
    open_questions = sum(_open_question_count(row.extracted_data) for row in extractions)
    unposted_drafts = int(
        (
            await db.execute(
                select(func.count(JournalEntry.id)).where(
                    JournalEntry.entity_id == entity.id,
                    JournalEntry.status == JournalEntryStatus.draft,
                    JournalEntry.source_transaction_id.is_not(None),
                )
            )
        ).scalar_one()
        or 0
    )

    if needs_review:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="documents_need_review",
                severity=AlertSeverity.warning,
                title="Documents need review",
                message=f"{len(needs_review)} uploaded document(s) still need review.",
                payload={"count": len(needs_review)},
            )
        )
    if duplicate_count:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="duplicate_documents_detected",
                severity=AlertSeverity.warning,
                title="Possible duplicate documents detected",
                message=f"{duplicate_count} extraction(s) were flagged as possible duplicates.",
                payload={"count": duplicate_count},
            )
        )
    if open_questions:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="document_questions_open",
                severity=AlertSeverity.info,
                title="Accounting questions are waiting for answers",
                message=f"{open_questions} question(s) remain open across extracted items.",
                payload={"count": open_questions},
            )
        )
    if low_confidence:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="low_confidence_documents",
                severity=AlertSeverity.info,
                title="Low-confidence extractions need confirmation",
                message=f"{len(low_confidence)} extraction(s) are still low confidence.",
                payload={"count": len(low_confidence)},
            )
        )
    if unposted_drafts:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="unposted_source_drafts",
                severity=AlertSeverity.info,
                title="Draft accounting records are still unposted",
                message=f"{unposted_drafts} source-linked draft journal entr{ 'y' if unposted_drafts == 1 else 'ies' } remain unposted.",
                payload={"count": unposted_drafts},
            )
        )
    return alerts


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
        actuals = await budget_actuals(db, entity_id=entity.id, budget_id=budget.id)
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

    # --- Skill pack integration: room-for-error score ---
    try:
        from app.skills.personal_finance.calculations.room_for_error import (  # noqa: PLC0415
            calculate_room_for_error_score,
        )

        profile = {
            "emergency_fund_months": float(dashboard.emergency_fund_months),
            "debt_to_income_ratio": (
                float(dashboard.total_debt / dashboard.monthly_income)
                if getattr(dashboard, "monthly_income", None) and dashboard.monthly_income > 0
                else 0.0
            ),
        }
        rfe = calculate_room_for_error_score(profile)
        # Attach result to the run summary as extra data; does not create an alert on its own.
        if run.summary is None:
            run.summary = {}
        run.summary.setdefault("skill_room_for_error", {})[str(entity.id)] = rfe
        if rfe.get("risk_level") == "high":
            alerts.append(
                await _create_alert(
                    db,
                    run=run,
                    entity_id=entity.id,
                    alert_type="room_for_error_high_risk",
                    severity=AlertSeverity.warning,
                    title="Financial room-for-error score is high-risk",
                    message=f"Score {rfe['score']}/100. Issues: {'; '.join(rfe['issues']) or 'none'}",
                    payload=rfe,
                )
            )
    except Exception:  # noqa: BLE001
        pass

    alerts.extend(await _document_review_alerts(db, run=run, entity=entity))
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

    # --- Skill pack integration: anomaly detection stub ---
    try:
        from app.skills.python_finance.analytics.anomalies import (  # noqa: PLC0415
            detect_amount_anomalies,
        )

        anomaly_result = detect_amount_anomalies([])
        if run.summary is None:
            run.summary = {}
        run.summary.setdefault("skill_anomaly_detection", {})[str(entity.id)] = anomaly_result
    except Exception:  # noqa: BLE001
        pass

    alerts.extend(await _document_review_alerts(db, run=run, entity=entity))
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
    # --- Skill pack integration: income statement stub from skill pack ---
    skill_income_stmt: dict = {}
    try:
        from app.skills.accounting.ledger.financial_statements import (  # noqa: PLC0415
            generate_income_statement,
        )

        # Called with empty lists as a stub; real ledger data lives in the DB service above.
        skill_income_stmt = generate_income_statement([], [])
        skill_income_stmt["from_ledger_service"] = True
    except Exception:  # noqa: BLE001
        pass

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
            *(
                [f"- Skill income statement (stub): revenue={skill_income_stmt.get('revenue', 'n/a')}, expenses={skill_income_stmt.get('expenses', 'n/a')}"]
                if skill_income_stmt
                else []
            ),
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


async def _tax_reserve_check(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity: Entity,
    as_of: date,
) -> list[Alert]:
    alerts: list[Alert] = []
    report = await tax_reserve_report(db, entity_id=entity.id, as_of=as_of)
    tax_reserves = await list_tax_reserves(db, entity_id=entity.id)

    if not tax_reserves:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="tax_reserve_missing",
                severity=AlertSeverity.info,
                title="Tax reserve record is missing",
                message="No tax reserve estimate has been recorded for this business.",
            )
        )
        return alerts

    if report.reserved_balance < report.latest_estimated_tax:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="tax_reserve_gap",
                severity=AlertSeverity.warning,
                title="Tax reserve is below estimated need",
                message=f"Tax reserve gap is {report.reserve_gap}.",
                payload={
                    "reserved_balance": str(report.reserved_balance),
                    "estimated_tax": str(report.latest_estimated_tax),
                    "reserve_gap": str(report.reserve_gap),
                },
            )
        )
    return alerts


async def _cash_runway_check(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity: Entity,
    as_of: date,
) -> list[Alert]:
    report = await runway_report(db, entity_id=entity.id, as_of=as_of)
    if report.monthly_expenses == Decimal("0"):
        return []

    severity: AlertSeverity | None = None
    title: str | None = None
    if report.runway_months < Decimal("1"):
        severity = AlertSeverity.critical
        title = "Business cash runway is below one month"
    elif report.runway_months < Decimal("2"):
        severity = AlertSeverity.warning
        title = "Business cash runway is below two months"
    elif report.runway_months < Decimal("3"):
        severity = AlertSeverity.info
        title = "Business cash runway is below three months"

    if severity is None or title is None:
        return []

    return [
        await _create_alert(
            db,
            run=run,
            entity_id=entity.id,
            alert_type="cash_runway_low",
            severity=severity,
            title=title,
            message=f"Operating cash covers {report.runway_months} months of expenses.",
            payload={
                "cash_balance": str(report.cash_balance),
                "monthly_expenses": str(report.monthly_expenses),
                "runway_months": str(report.runway_months),
            },
        )
    ]


async def _budget_overspend_check(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity: Entity,
    as_of: date,
) -> list[Alert]:
    active_budgets = [
        budget
        for budget in await list_budgets(db, entity_id=entity.id)
        if budget.period_start <= as_of <= budget.period_end
    ]
    if not active_budgets:
        return []

    budget = sorted(active_budgets, key=lambda item: item.period_start, reverse=True)[0]
    actuals = await budget_actuals(db, entity_id=entity.id, budget_id=budget.id)
    alerts: list[Alert] = []
    for line in actuals.lines:
        if not line.overspent:
            continue
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="budget_overspend",
                severity=AlertSeverity.warning,
                title=f"Budget overspend: {line.account_code} {line.account_name}",
                message=(
                    f"Overspend on {line.account_code} {line.account_name}: "
                    f"actual {line.actual_amount} vs planned {line.planned_amount}"
                ),
                payload={
                    "budget_id": str(budget.id),
                    "account_id": str(line.account_id),
                    "account_code": line.account_code,
                    "account_name": line.account_name,
                    "actual_amount": str(line.actual_amount),
                    "planned_amount": str(line.planned_amount),
                },
            )
        )
    return alerts


async def _ar_ap_aging_check(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity: Entity,
    as_of: date,
) -> list[Alert]:
    alerts: list[Alert] = []
    ar = await ar_aging(db, entity_id=entity.id, as_of=as_of)
    for row in [aging_row for aging_row in ar.rows if aging_row.days_91_plus > Decimal("0")][:5]:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="ar_aging_91_plus",
                severity=AlertSeverity.warning,
                title=f"AR over 91 days: {row.counterparty_name}",
                message=f"{row.counterparty_name} has {row.balance_due} outstanding over 91 days.",
                payload={
                    "number": row.number,
                    "counterparty_name": row.counterparty_name,
                    "balance_due": str(row.balance_due),
                    "days_91_plus": str(row.days_91_plus),
                },
            )
        )

    ap = await ap_aging(db, entity_id=entity.id, as_of=as_of)
    for row in [aging_row for aging_row in ap.rows if aging_row.days_91_plus > Decimal("0")][:5]:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="ap_aging_91_plus",
                severity=AlertSeverity.warning,
                title=f"AP over 91 days: {row.counterparty_name}",
                message=f"{row.counterparty_name} has {row.balance_due} payable over 91 days.",
                payload={
                    "number": row.number,
                    "counterparty_name": row.counterparty_name,
                    "balance_due": str(row.balance_due),
                    "days_91_plus": str(row.days_91_plus),
                },
            )
        )
    return alerts


async def _weekly_personal_report(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity: Entity,
    as_of: date,
) -> list[Alert]:
    period_end = as_of
    period_start = as_of - timedelta(days=6)
    dashboard = await personal_dashboard(db, entity_id=entity.id, as_of=as_of)
    debt_plan = await debt_payoff_plan(db, entity_id=entity.id, as_of=as_of)
    emergency_plan = await emergency_fund_plan(db, entity_id=entity.id, as_of=as_of)

    # --- Skill pack integration: weekly money meeting agenda ---
    agenda_lines: list[str] = []
    try:
        from app.skills.personal_finance.meetings.weekly_money_meeting import (  # noqa: PLC0415
            build_weekly_money_meeting_agenda,
        )

        context = {
            "has_business": False,  # personal entity; cross-entity check omitted here
            "has_debt": debt_plan.total_debt > Decimal("0"),
            "has_open_questions": False,
        }
        agenda_result = build_weekly_money_meeting_agenda(context)
        agenda_lines = agenda_result.get("agenda", [])
    except Exception:  # noqa: BLE001
        pass

    agenda_section = (
        "\n## Weekly Money Meeting Agenda\n" + "\n".join(f"- {item}" for item in agenda_lines)
        if agenda_lines
        else ""
    )

    body = "\n".join(
        [
            f"# Weekly Personal Report: {entity.name}",
            f"- Period: {period_start.isoformat()} to {period_end.isoformat()}",
            f"- Net worth: {dashboard.net_worth}",
            f"- Monthly income: {dashboard.monthly_income}",
            f"- Monthly expenses: {dashboard.monthly_expenses}",
            f"- Monthly savings: {dashboard.monthly_savings}",
            f"- Emergency fund balance: {dashboard.emergency_fund_balance}",
            f"- Emergency fund coverage months: {dashboard.emergency_fund_months}",
            f"- Emergency fund gap to minimum: {emergency_plan.gap_to_minimum}",
            f"- Total debt: {debt_plan.total_debt}",
            f"- Active debts in payoff plan: {len(debt_plan.debts)}",
        ]
    ) + agenda_section

    db.add(
        GeneratedReport(
            tenant_id=run.tenant_id,
            entity_id=entity.id,
            heartbeat_run_id=run.id,
            report_kind=ReportKind.weekly_personal_report,
            period_start=period_start,
            period_end=period_end,
            title=f"Weekly personal report for {entity.name}",
            body=body,
        )
    )
    await db.flush()

    if dashboard.emergency_fund_months < Decimal("1"):
        return [
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="emergency_fund_low",
                severity=AlertSeverity.info,
                title="Emergency fund is below one month",
                message="Weekly personal report flagged reserves below one month of expenses.",
                payload={"emergency_fund_months": str(dashboard.emergency_fund_months)},
            )
        ]
    return []


async def _monthly_personal_close(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity: Entity,
    as_of: date,
) -> list[Alert]:
    existing = (
        await db.execute(
            select(NetWorthSnapshot).where(
                NetWorthSnapshot.entity_id == entity.id,
                NetWorthSnapshot.as_of == as_of,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        await create_net_worth_snapshot(db, entity_id=entity.id, as_of=as_of)

    # --- Skill pack integration: emergency fund plan from skill pack ---
    try:
        from app.skills.personal_finance.calculations.emergency_fund import (  # noqa: PLC0415
            emergency_fund_plan as skill_emergency_fund_plan,
        )

        dashboard = await personal_dashboard(db, entity_id=entity.id, as_of=as_of)
        monthly_expenses = float(dashboard.monthly_expenses)
        current_fund = float(dashboard.emergency_fund_balance)
        skill_plan = skill_emergency_fund_plan(
            monthly_essential_expenses=monthly_expenses,
            current_fund=current_fund,
        )
        if run.summary is None:
            run.summary = {}
        run.summary.setdefault("skill_emergency_fund_plan", {})[str(entity.id)] = skill_plan
    except Exception:  # noqa: BLE001
        pass

    return []


async def _monthly_business_close(
    db: AsyncSession,
    *,
    run: HeartbeatRun,
    entity: Entity,
    as_of: date,
) -> list[Alert]:
    alerts: list[Alert] = []
    checklist = await closing_checklist(db, entity_id=entity.id, as_of=as_of)
    unposted_drafts = (
        await db.execute(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.entity_id == entity.id,
                JournalEntry.status == JournalEntryStatus.draft,
            )
        )
    ).scalar_one()
    if unposted_drafts > 0:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="monthly_close_unposted_drafts",
                severity=AlertSeverity.info,
                title="Monthly close has unposted drafts",
                message=f"{unposted_drafts} draft journal entries remain unposted.",
                payload={"unposted_drafts": int(unposted_drafts)},
            )
        )

    tax_report = await tax_reserve_report(db, entity_id=entity.id, as_of=as_of)
    if checklist.tax_reserve_balance < tax_report.latest_estimated_tax:
        alerts.append(
            await _create_alert(
                db,
                run=run,
                entity_id=entity.id,
                alert_type="tax_reserve_gap",
                severity=AlertSeverity.warning,
                title="Tax reserve is below estimated need",
                message=f"Monthly close found a tax reserve gap of {tax_report.reserve_gap}.",
                payload={
                    "tax_reserve_balance": str(checklist.tax_reserve_balance),
                    "estimated_tax": str(tax_report.latest_estimated_tax),
                    "reserve_gap": str(tax_report.reserve_gap),
                },
            )
        )
    return alerts
