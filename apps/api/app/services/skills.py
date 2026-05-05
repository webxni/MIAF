from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import FinClawError, NotFoundError
from app.models import EntityMode, SkillRunLog, SkillState
from app.services.business import ap_aging, ar_aging, business_dashboard, closing_checklist, list_tax_reserves
from app.services.heartbeat import list_reports
from app.services.memory import list_memories
from app.services.personal import list_debts, list_investment_accounts, personal_dashboard

_SKILL_ROOT_CANDIDATES = [
    Path(__file__).resolve().parents[4] / "skills",
    Path(__file__).resolve().parents[2] / "skills",
]

_ALLOWED_PERMISSIONS = {
    "read_transactions",
    "write_drafts",
    "post_entries",
    "read_documents",
    "write_documents",
    "read_memory",
    "write_memory",
    "read_reports",
    "send_messages",
}


class SkillManifest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=32)
    description: str = Field(min_length=1, max_length=500)
    mode: Literal["personal", "business", "both"]
    permissions: list[str]
    triggers: list[str]
    tools_used: list[str]
    requires_confirmation: bool
    risk_level: Literal["low", "medium", "high"]
    entrypoint: str = Field(min_length=1, max_length=200)


@dataclass
class LoadedSkill:
    manifest: SkillManifest
    path: Path
    builtin: bool = True


def _require_permissions(skill: LoadedSkill, *required: str) -> None:
    missing = [permission for permission in required if permission not in skill.manifest.permissions]
    if missing:
        raise FinClawError(
            f"Skill {skill.manifest.name} is missing required permission(s): {missing}",
            code="skill_permission_denied",
            details={"skill_name": skill.manifest.name, "missing_permissions": missing},
        )


def load_skill_manifests() -> list[LoadedSkill]:
    loaded: list[LoadedSkill] = []
    skills_root = next((path for path in _SKILL_ROOT_CANDIDATES if path.exists()), None)
    if skills_root is None:
        return loaded
    for manifest_path in sorted(skills_root.glob("*/SKILL.yaml")):
        data = json.loads(manifest_path.read_text())
        manifest = SkillManifest.model_validate(data)
        unknown = set(manifest.permissions) - _ALLOWED_PERMISSIONS
        if unknown:
            raise FinClawError(
                f"Unknown skill permission(s): {sorted(unknown)}",
                code="skill_permission_invalid",
            )
        loaded.append(LoadedSkill(manifest=manifest, path=manifest_path.parent, builtin=True))
    return loaded


async def list_skill_manifests(db: AsyncSession, *, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    loaded = load_skill_manifests()
    states = {
        row.skill_name: row
        for row in (
            await db.execute(select(SkillState).where(SkillState.tenant_id == tenant_id))
        ).scalars().all()
    }
    items: list[dict[str, Any]] = []
    for skill in loaded:
        state = states.get(skill.manifest.name)
        enabled = state.enabled if state is not None else skill.builtin
        items.append({**skill.manifest.model_dump(), "builtin": skill.builtin, "enabled": enabled})
    return items


async def set_skill_enabled(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    skill_name: str,
    enabled: bool,
) -> SkillState:
    loaded = {skill.manifest.name: skill for skill in load_skill_manifests()}
    if skill_name not in loaded:
        raise NotFoundError(f"Skill {skill_name} not found", code="skill_not_found")
    state = (
        await db.execute(
            select(SkillState).where(SkillState.tenant_id == tenant_id, SkillState.skill_name == skill_name)
        )
    ).scalar_one_or_none()
    if state is None:
        state = SkillState(
            tenant_id=tenant_id,
            skill_name=skill_name,
            enabled=enabled,
            installed_version=loaded[skill_name].manifest.version,
            is_builtin=loaded[skill_name].builtin,
        )
        db.add(state)
    else:
        state.enabled = enabled
        state.installed_version = loaded[skill_name].manifest.version
    await db.flush()
    return state


async def run_skill(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    skill_name: str,
    input_payload: dict,
) -> SkillRunLog:
    loaded = {skill.manifest.name: skill for skill in load_skill_manifests()}
    if skill_name not in loaded:
        raise NotFoundError(f"Skill {skill_name} not found", code="skill_not_found")
    skill = loaded[skill_name]

    state = (
        await db.execute(
            select(SkillState).where(SkillState.tenant_id == tenant_id, SkillState.skill_name == skill_name)
        )
    ).scalar_one_or_none()
    enabled = state.enabled if state is not None else skill.builtin
    if not enabled:
        raise FinClawError("Skill is disabled", code="skill_disabled")

    output_payload = await _execute_skill(db, tenant_id=tenant_id, entity_id=entity_id, skill=skill, input_payload=input_payload)
    row = SkillRunLog(
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=entity_id,
        skill_name=skill_name,
        skill_version=skill.manifest.version,
        permissions=skill.manifest.permissions,
        input_payload=input_payload,
        output_payload=output_payload,
        result_status="completed",
    )
    db.add(row)
    await db.flush()
    return row


async def list_skill_runs(db: AsyncSession, *, tenant_id: uuid.UUID, limit: int = 50) -> list[SkillRunLog]:
    return list(
        (
            await db.execute(
                select(SkillRunLog)
                .where(SkillRunLog.tenant_id == tenant_id)
                .order_by(SkillRunLog.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    )


async def _execute_skill(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    skill: LoadedSkill,
    input_payload: dict,
) -> dict[str, Any]:
    name = skill.manifest.name
    as_of = input_payload.get("as_of") or date.today()
    mode = input_payload.get("mode")

    if name == "receipt_reader":
        _require_permissions(skill, "read_documents")
        fields = input_payload.get("fields") or {}
        return {
            "document_kind": "receipt",
            "merchant": fields.get("merchant"),
            "date": fields.get("date"),
            "total": fields.get("total"),
            "confidence": fields.get("confidence", {}),
            "status": "review_required" if not fields else "parsed",
        }
    if name == "invoice_reader":
        _require_permissions(skill, "read_documents")
        fields = input_payload.get("fields") or {}
        return {
            "document_kind": "invoice",
            "vendor_or_customer": fields.get("vendor") or fields.get("customer"),
            "invoice_number": fields.get("invoice_number"),
            "due_date": fields.get("due_date"),
            "total": fields.get("total"),
            "status": "review_required" if not fields else "parsed",
        }
    if name == "transaction_classifier":
        _require_permissions(skill, "read_transactions")
        description = str(input_payload.get("description", "")).lower()
        entity_mode = "business" if any(token in description for token in ["client", "invoice", "vendor", "rent"]) else "personal"
        category = "owner_draw" if "owner draw" in description else "expense"
        return {
            "description": input_payload.get("description"),
            "suggested_mode": entity_mode,
            "suggested_category": category,
            "confidence": "medium",
        }
    if name == "emergency_fund_planner":
        _require_permissions(skill, "read_transactions", "read_reports")
        if entity_id is None:
            raise FinClawError("entity_id is required", code="entity_required")
        dashboard = await personal_dashboard(db, entity_id=entity_id, as_of=as_of)
        return {
            "emergency_fund_months": str(dashboard.emergency_fund_months),
            "monthly_expenses": str(dashboard.monthly_expenses),
            "recommendation": "Build reserves to at least 3-6 months of essential expenses.",
        }
    if name == "debt_payoff_planner":
        _require_permissions(skill, "read_transactions", "read_reports")
        if entity_id is None:
            raise FinClawError("entity_id is required", code="entity_required")
        debts = await list_debts(db, entity_id=entity_id)
        ordered = sorted(debts, key=lambda item: (item.interest_rate_apr or 0, item.current_balance), reverse=True)
        return {
            "strategy": "avalanche",
            "debts": [
                {
                    "name": debt.name,
                    "balance": str(debt.current_balance),
                    "interest_rate_apr": str(debt.interest_rate_apr or 0),
                }
                for debt in ordered
            ],
        }
    if name == "investment_allocator":
        _require_permissions(skill, "read_transactions", "read_reports")
        if entity_id is None:
            raise FinClawError("entity_id is required", code="entity_required")
        dashboard = await personal_dashboard(db, entity_id=entity_id, as_of=as_of)
        accounts = await list_investment_accounts(db, entity_id=entity_id)
        return {
            "investment_value": str(dashboard.investment_value),
            "allocation": [
                {
                    "label": row.label,
                    "value": str(row.value),
                    "allocation_ratio": str(row.allocation_ratio),
                }
                for row in dashboard.investment_allocation
            ],
            "accounts_tracked": len(accounts),
            "disclaimer": dashboard.investment_disclaimer,
        }
    if name == "business_health_advisor":
        _require_permissions(skill, "read_transactions", "read_reports")
        if entity_id is None:
            raise FinClawError("entity_id is required", code="entity_required")
        dashboard = await business_dashboard(db, entity_id=entity_id, as_of=as_of)
        return {
            "cash_balance": str(dashboard.cash_balance),
            "monthly_net_income": str(dashboard.monthly_net_income),
            "ar": str(dashboard.accounts_receivable),
            "ap": str(dashboard.accounts_payable),
            "advice": "Watch cash runway, tax reserve coverage, and overdue receivables.",
        }
    if name == "ar_collector":
        _require_permissions(skill, "read_reports", "send_messages")
        if entity_id is None:
            raise FinClawError("entity_id is required", code="entity_required")
        aging = await ar_aging(db, entity_id=entity_id, as_of=as_of)
        return {
            "customer_count": len(aging.rows),
            "overdue_count": sum(1 for row in aging.rows if row.days_past_due > 0),
            "total_due": str(aging.total_due),
            "next_action": "Follow up on overdue invoices first.",
        }
    if name == "ap_scheduler":
        _require_permissions(skill, "read_reports", "send_messages")
        if entity_id is None:
            raise FinClawError("entity_id is required", code="entity_required")
        aging = await ap_aging(db, entity_id=entity_id, as_of=as_of)
        return {
            "vendor_count": len(aging.rows),
            "overdue_count": sum(1 for row in aging.rows if row.days_past_due > 0),
            "total_due": str(aging.total_due),
            "next_action": "Prioritize overdue bills and protect runway.",
        }
    if name == "tax_reserve_estimator":
        _require_permissions(skill, "read_reports")
        if entity_id is None:
            raise FinClawError("entity_id is required", code="entity_required")
        reserves = await list_tax_reserves(db, entity_id=entity_id)
        latest = reserves[0] if reserves else None
        return {
            "reserve_count": len(reserves),
            "latest_estimated_tax": str(latest.estimated_tax) if latest else None,
            "latest_reserved_amount": str(latest.reserved_amount) if latest else None,
            "status": "estimate_only",
        }
    if name == "monthly_close_assistant":
        _require_permissions(skill, "read_reports")
        if entity_id is None:
            raise FinClawError("entity_id is required", code="entity_required")
        checklist = await closing_checklist(db, entity_id=entity_id, as_of=as_of)
        return {
            "items": [item.model_dump(mode="json") for item in checklist.items],
            "all_complete": checklist.all_complete,
        }
    if name == "anomaly_detector":
        _require_permissions(skill, "read_reports")
        if entity_id is None:
            raise FinClawError("entity_id is required", code="entity_required")
        if mode == EntityMode.personal.value:
            dashboard = await personal_dashboard(db, entity_id=entity_id, as_of=as_of)
            anomalies: list[str] = []
            if dashboard.savings_rate < 0:
                anomalies.append("Savings rate is negative this month.")
            if dashboard.emergency_fund_months < 1:
                anomalies.append("Emergency fund coverage is below one month.")
            return {"mode": "personal", "anomalies": anomalies}
        dashboard = await business_dashboard(db, entity_id=entity_id, as_of=as_of)
        anomalies = []
        if dashboard.monthly_net_income < 0:
            anomalies.append("Monthly net income is negative.")
        if dashboard.accounts_payable > dashboard.cash_balance:
            anomalies.append("Accounts payable exceeds cash on hand.")
        return {"mode": "business", "anomalies": anomalies}
    if name == "weekly_reporter":
        _require_permissions(skill, "read_reports", "send_messages")
        reports = await list_reports(db, tenant_id=tenant_id, limit=1)
        return {
            "latest_report_title": reports[0].title if reports else None,
            "latest_report_kind": reports[0].report_kind.value if reports else None,
            "report_count": len(reports),
        }
    if name == "personal_budget_coach":
        _require_permissions(skill, "read_transactions", "read_memory", "read_reports")
        related = await list_memories(db, tenant_id=tenant_id, query="budget", limit=5)
        return {
            "memory_matches": [row.title for row in related],
            "coaching_note": "Keep budget categories aligned with real expense accounts and review overspends weekly.",
        }
    return {"status": "not_implemented"}
