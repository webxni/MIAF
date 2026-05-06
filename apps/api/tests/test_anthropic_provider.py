from __future__ import annotations

from types import SimpleNamespace

import anthropic
import pytest

from app.schemas.agent import AgentChatRequest
from app.services.agent import AnthropicProvider, HeuristicProvider, PlannedToolCall

pytestmark = pytest.mark.asyncio


async def test_no_key_falls_back_to_heuristic(seeded, db, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    request = AgentChatRequest(message="Explain the balance sheet.")

    provider = AnthropicProvider()
    heuristic = HeuristicProvider()

    assert await provider.plan(request, api_key=None) == await heuristic.plan(request)


async def test_anthropic_provider_uses_real_client_when_key_set(seeded, db, monkeypatch):
    recorded: dict[str, object] = {}

    class FakeMessages:
        def create(self, **kwargs):
            recorded["create_kwargs"] = kwargs
            return SimpleNamespace(
                content=[
                    {"type": "text", "text": "Plan ready."},
                    {
                        "type": "tool_use",
                        "name": "get_balance_sheet",
                        "input": {"as_of": "2026-05-06"},
                    },
                ]
            )

    class FakeAnthropic:
        def __init__(self, *, api_key):
            recorded["api_key"] = api_key
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)

    provider = AnthropicProvider()
    message, planned, disclaimers = await provider.plan(
        AgentChatRequest(message="Explain the balance sheet."),
        api_key="test-key",
        model="custom-model",
    )

    assert recorded["api_key"] == "test-key"
    create_kwargs = recorded["create_kwargs"]
    assert create_kwargs["model"] == "custom-model"
    assert create_kwargs["messages"] == [{"role": "user", "content": "Explain the balance sheet."}]
    assert create_kwargs["max_tokens"] == 1024
    assert create_kwargs["tools"]
    assert message == "Plan ready."
    assert planned == [PlannedToolCall(tool_name="get_balance_sheet", arguments={"as_of": "2026-05-06"})]
    assert disclaimers == []


async def test_anthropic_provider_falls_back_on_exception(seeded, db, monkeypatch):
    class FailingMessages:
        def create(self, **kwargs):
            raise RuntimeError("boom")

    class FailingAnthropic:
        def __init__(self, *, api_key):
            self.messages = FailingMessages()

    monkeypatch.setattr(anthropic, "Anthropic", FailingAnthropic)

    request = AgentChatRequest(message="Explain the balance sheet.")
    provider = AnthropicProvider()
    heuristic = HeuristicProvider()

    assert await provider.plan(request, api_key="test-key") == await heuristic.plan(request)
