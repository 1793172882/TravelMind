"""Tests for the real LangChain/LangGraph runtime with a Fake model."""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.agent.runtime import build_agent_runtime, build_default_registry
from app.agent.state import AgentContext
from app.harness.tool_registry import ToolRegistry


@pytest.mark.anyio
async def test_agent_runtime_uses_thread_context() -> None:
    runtime = build_agent_runtime(
        model=FakeListChatModel(responses=["你好，我是 TravelMind。"]),
        registry=ToolRegistry(),
    )

    result = await runtime.chat(
        "你好",
        AgentContext(user_id="user-1", thread_id="thread-1"),
    )

    assert result.status == "completed"
    assert result.message == "你好，我是 TravelMind。"


def test_default_registry_exposes_read_and_approved_write_tools() -> None:
    tools = {tool.name: tool for tool in build_default_registry().list_tools()}

    assert tools["trip.get"].risk_level.value == "read"
    assert tools["trip.create"].risk_level.value == "write"
    assert tools["trip.add_itinerary_item"].risk_level.value == "write"
