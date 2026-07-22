"""Checks for the product features layered on the single-Agent Harness."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import SecretStr

from app.agent.state import AgentContext
from app.config import settings
from app.harness.events import EventBroker
from app.harness.memory import MemoryStore, UserPreference
from app.harness.runtime_context import current_agent_context
from app.harness.scheduler import schedule_trip_weather_checks
from app.harness.tasks import TaskStore, new_task
from app.infrastructure.outbox import OutboxWorker
from app.services.auth import hash_password, issue_token, parse_token, verify_password


def test_password_token_and_user_scoping(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_secret", SecretStr("test-secret-with-enough-entropy"))
    encoded = hash_password("correct horse battery staple")
    user = SimpleNamespace(id=7, username="traveler")

    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)
    identity = parse_token(issue_token(user))
    assert identity.user_id == "web:7"
    assert identity.thread_id("summer") == "web:7:summer"


def test_memory_tasks_and_events_are_wired() -> None:
    memory = MemoryStore()
    merged = memory.merge(
        "web:7",
        UserPreference(preferred_transport=["地铁"], travels_with_elderly=True),
    )
    assert merged.preferred_transport == ["地铁"]

    store = TaskStore()
    token = current_agent_context.set(AgentContext("web:7", "web:7:summer"))
    try:
        task = new_task("检查路线", [])
        store.add(task)
    finally:
        current_agent_context.reset(token)
    assert store.runnable(user_id="web:7", thread_id="web:7:summer") == [task]


@pytest.mark.anyio
async def test_event_broker_and_outbox_worker() -> None:
    broker = EventBroker()
    event = await broker.publish("thread-1", "tool.completed", tool="amap.weather")
    assert broker.history("thread-1")[0] == event

    outbox_event = SimpleNamespace(
        id=1,
        status="pending",
        topic="mcp.call_tool",
        payload={"tool": "lark.send", "arguments": {"text": "ok"}},
    )
    store = SimpleNamespace(
        get=Mock(return_value=outbox_event),
        succeed=Mock(),
        fail=Mock(),
    )
    manager = SimpleNamespace(call_tool=AsyncMock())

    assert await OutboxWorker(store, manager).dispatch(1)
    manager.call_tool.assert_awaited_once_with("lark.send", {"text": "ok"})
    store.succeed.assert_called_once_with(1)


def test_trip_creation_schedules_two_weather_checks() -> None:
    session = Mock()
    session.scalar.return_value = None
    trip = SimpleNamespace(
        id=10,
        owner_id="web:7",
        thread_id="web:7:summer",
        start_at=datetime.now() + timedelta(days=2),
    )

    schedule_trip_weather_checks(session, trip)

    assert session.add.call_count == 2
