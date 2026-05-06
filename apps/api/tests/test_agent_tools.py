"""Tests for agent tool enhancements: OpenAI provider, SkillPlanner, and heartbeat resilience."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.api.deps import CurrentUser
from app.models import Session, User
from app.schemas.agent import AgentChatRequest, RoomForErrorArgs
from app.services.agent import (
    AgentService,
    HeuristicProvider,
    OpenAIProvider,
    SkillPlanner,
    ToolContext,
    _tool_check_room_for_error,
    build_tool_registry,
)

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


async def test_openai_provider_falls_back_to_heuristic_without_key():
    """OpenAIProvider without a key must fall back to HeuristicProvider output."""
    provider = OpenAIProvider()
    request = AgentChatRequest(message="Show me the balance sheet")
    message, calls, disclaimers = await provider.plan(request, api_key=None)
    # HeuristicProvider handles "balance sheet" → get_balance_sheet
    assert any(c.tool_name == "get_balance_sheet" for c in calls)


def test_openai_tool_schema_format():
    """OpenAI tool schema must use {"type":"function","function":{...}} envelope."""
    from app.services.agent import _tool_to_openai_schema

    registry = build_tool_registry()
    tools = registry.list_tools()
    assert tools, "Registry must have at least one tool"

    for tool in tools:
        schema = _tool_to_openai_schema(tool)
        assert schema["type"] == "function"
        assert "function" in schema
        fn = schema["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert isinstance(fn["parameters"], dict)


def test_skill_planner_suggests_tools_for_known_intents():
    """SkillPlanner must return non-empty suggestions for known keywords."""
    planner = SkillPlanner()

    suggestions = planner.suggest("Show me the balance sheet")
    assert "generate_balance_sheet_data" in suggestions

    suggestions = planner.suggest("Check my emergency fund status")
    assert "suggest_emergency_fund_plan" in suggestions
    assert "check_room_for_error" in suggestions

    suggestions = planner.suggest("Analyze spending anomalies")
    assert "detect_financial_anomalies" in suggestions

    empty = planner.suggest("hello world")
    assert empty == []


async def test_check_room_for_error_includes_memory_suggestion_on_medium_risk(seeded, db):
    """check_room_for_error must include memory_suggestion when risk is medium or high."""
    me = await _current_user(db, seeded)
    request = AgentChatRequest(message="")
    ctx = ToolContext(db=db, me=me, request=request)

    # Profile that triggers medium risk: emergency fund < 3 months (-25) + high DTI (-20) → score 55
    args = RoomForErrorArgs(profile={
        "emergency_fund_months": 1.0,
        "debt_to_income_ratio": 0.40,
        "business_income_dependency": 0.0,
        "tax_reserve_gap": 0,
    })
    result = await _tool_check_room_for_error(ctx, args)

    assert result["risk_level"] in {"medium", "high"}
    assert "memory_suggestion" in result
    assert "score" in result["memory_suggestion"]["content"]


async def test_agent_service_initializes_with_skill_planner(seeded, db):
    """AgentService must expose a SkillPlanner instance."""
    service = AgentService()
    assert isinstance(service.skill_planner, SkillPlanner)

    # SkillPlanner suggestions should propagate to the log path without error.
    me = await _current_user(db, seeded)
    response = await service.chat(
        db,
        me=me,
        payload=AgentChatRequest(message="Analyze spending anomalies in my transactions"),
    )
    # Response must be valid even with an empty transaction list (no anomalies found).
    assert response.message
    assert response.provider
