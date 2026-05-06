from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.errors import MIAFError
from app.models import HeartbeatType, MemoryType, SkillRunLog, SkillState
from app.schemas.memory import MemoryCreate
from app.services.heartbeat import run_heartbeat
from app.services.memory import create_memory
from app.services.skills import (
    LoadedSkill,
    SkillManifest,
    list_skill_manifests,
    load_skill_manifests,
    run_skill,
    set_skill_enabled,
)

pytestmark = pytest.mark.asyncio


async def test_builtin_skills_load_and_list_for_tenant(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])

    manifests = load_skill_manifests()
    names = {row.manifest.name for row in manifests}

    assert {
        "receipt_reader",
        "invoice_reader",
        "transaction_classifier",
        "personal_budget_coach",
        "emergency_fund_planner",
        "debt_payoff_planner",
        "investment_allocator",
        "business_health_advisor",
        "ar_collector",
        "ap_scheduler",
        "tax_reserve_estimator",
        "monthly_close_assistant",
        "anomaly_detector",
        "weekly_reporter",
    }.issubset(names)

    listed = await list_skill_manifests(db, tenant_id=tenant_id)
    assert len(listed) == len(manifests)
    assert all(item["builtin"] is True for item in listed)
    assert all(item["enabled"] is True for item in listed)


async def test_skill_enable_disable_persists_state(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])

    state = await set_skill_enabled(
        db,
        tenant_id=tenant_id,
        skill_name="personal_budget_coach",
        enabled=False,
    )
    assert state.enabled is False

    row = (
        await db.execute(
            select(SkillState).where(
                SkillState.tenant_id == tenant_id,
                SkillState.skill_name == "personal_budget_coach",
            )
        )
    ).scalar_one()
    assert row.installed_version == "0.1.0"
    assert row.is_builtin is True

    enabled_again = await set_skill_enabled(
        db,
        tenant_id=tenant_id,
        skill_name="personal_budget_coach",
        enabled=True,
    )
    assert enabled_again.enabled is True


async def test_skill_run_logs_memory_backed_budget_coaching(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])

    await create_memory(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=MemoryCreate(
            memory_type=MemoryType.personal_preference,
            title="Budget cadence",
            content="Review the grocery and dining budget every Friday.",
            keywords=["budget", "groceries"],
            consent_granted=True,
        ),
    )

    row = await run_skill(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=None,
        skill_name="personal_budget_coach",
        input_payload={},
    )

    assert row.result_status == "completed"
    assert "read_memory" in row.permissions
    assert "Budget cadence" in row.output_payload["memory_matches"]

    logs = (await db.execute(select(SkillRunLog).where(SkillRunLog.tenant_id == tenant_id))).scalars().all()
    assert len(logs) == 1
    assert logs[0].skill_name == "personal_budget_coach"


async def test_weekly_reporter_skill_reads_latest_generated_report(seeded, db):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])

    await run_heartbeat(
        db,
        tenant_id=tenant_id,
        heartbeat_type=HeartbeatType.weekly_business_report,
        as_of=date(2026, 5, 5),
        trigger_source="manual",
        initiated_by_user_id=user_id,
    )

    row = await run_skill(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        entity_id=None,
        skill_name="weekly_reporter",
        input_payload={},
    )

    assert row.output_payload["latest_report_kind"] == "weekly_business_report"
    assert row.output_payload["report_count"] == 1


async def test_skill_permission_manifest_is_enforced(seeded, db, monkeypatch):
    tenant_id = uuid.UUID(seeded["tenant_id"])
    user_id = uuid.UUID(seeded["user_id"])

    broken_manifest = SkillManifest(
        name="weekly_reporter",
        version="0.1.0",
        description="Broken manifest for test.",
        mode="both",
        permissions=["read_reports"],
        triggers=["weekly report"],
        tools_used=["get_business_summary"],
        requires_confirmation=False,
        risk_level="low",
        entrypoint="handler.py",
    )

    def _fake_manifests() -> list[LoadedSkill]:
        return [LoadedSkill(manifest=broken_manifest, path=load_skill_manifests()[0].path, builtin=True)]

    monkeypatch.setattr("app.services.skills.load_skill_manifests", _fake_manifests)

    with pytest.raises(MIAFError) as exc:
        await run_skill(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            entity_id=None,
            skill_name="weekly_reporter",
            input_payload={},
        )

    assert exc.value.code == "skill_permission_denied"
