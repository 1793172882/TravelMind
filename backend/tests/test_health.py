from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient
from pydantic import SecretStr
import pytest

from app.api.dependencies import get_agent_runtime, get_trip_service
from app.api.routes.webhooks import _run_feishu_agent
from app.agent.state import AgentContext
from app.agent.runtime import AgentRunResult, TravelAgentRuntime
from app.main import app
from app.config import settings
from app.services.trip import TripService

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "TravelMind"}

def test_version() -> None:
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() ==  {'name': 'TravelMind', 'version': '0.1.0'}


def test_demo_ui_is_served() -> None:
    response = client.get("/ui/")

    assert response.status_code == 200
    assert "TravelMind" in response.text
    assert 'id="view-dashboard"' in response.text
    assert 'id="view-assistant"' in response.text
    assert 'id="view-trips"' in response.text
    assert 'id="view-knowledge"' in response.text
    assert 'id="create-trip-dialog"' in response.text


def test_trip_preview() -> None:
    # json 参数自动序列化为请求体
    payload = {
     "origin": "北京",
      "destination": "上海"    
      }
    response = client.post("/trips/preview", json=payload)
    # 断言
    assert response.status_code == 200

def test_trip_preview_rejects_empty_origin() -> None:
    payload = {
        "origin": "",
        "destination": "上海",
    }

    response = client.post("/trips/preview", json=payload)

    assert response.status_code == 422
    
def test_create_trip() -> None:
    service = Mock(spec=TripService)
    service.create_trip.return_value = SimpleNamespace(
        id=1001,
        origin="北京",
        destination="上海",
        start_at=None,
        end_at=None,
        budget=None,
        status="draft",
        created_at=datetime(2026, 7, 19, 10, 0),
        updated_at=datetime(2026, 7, 19, 10, 0),
    )
    app.dependency_overrides[get_trip_service] = lambda: service

    try:
        response = client.post(
            "/trips",
            json={"origin": "北京", "destination": "上海"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["id"] == 1001


def test_get_missing_trip_returns_404() -> None:
    service = Mock(spec=TripService)
    service.get_trip.return_value = None
    app.dependency_overrides[get_trip_service] = lambda: service

    try:
        response = client.get("/trips/9999")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Trip not found"}


def test_chat_endpoint_uses_agent_runtime() -> None:
    runtime = Mock(spec=TravelAgentRuntime)
    runtime.chat.return_value = AgentRunResult(
        status="completed",
        message="已收到你的出行需求。",
    )
    app.dependency_overrides[get_agent_runtime] = lambda: runtime

    try:
        response = client.post(
            "/chat",
            json={"message": "规划杭州一日游", "thread_id": "thread-1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "thread_id": "thread-1",
        "message": "已收到你的出行需求。",
        "status": "completed",
        "pending_approvals": [],
    }


def test_lifespan_and_feishu_webhook(monkeypatch, tmp_path) -> None:
    """The real app lifespan initializes channel/MCP state before callbacks."""
    monkeypatch.setattr(settings, "feishu_verification_token", SecretStr("verify-me"))
    monkeypatch.setattr(settings, "mcp_config_path", tmp_path / "missing-mcp.json")
    monkeypatch.setattr("app.main.ensure_application_tables", Mock())
    monkeypatch.setattr("app.main.build_knowledge_store", Mock())
    monkeypatch.setattr("app.main.EventDeduplicator", lambda **_: __import__(
        "app.channels.feishu", fromlist=["EventDeduplicator"]
    ).EventDeduplicator())
    checkpoint = AsyncMock()
    checkpoint.setup = AsyncMock()
    checkpoint_context = AsyncMock()
    checkpoint_context.__aenter__.return_value = checkpoint
    monkeypatch.setattr(
        "app.main.TravelMindMySQLSaver.from_conn_string",
        lambda _: checkpoint_context,
    )
    runtime = Mock(spec=TravelAgentRuntime)
    runtime.chat = AsyncMock(
        return_value=AgentRunResult(status="completed", message="规划已生成")
    )
    runtime.pending_approvals = AsyncMock(return_value=[])
    manager = SimpleNamespace(
        tools={"lark_openapi.im_v1_message_create": object()},
        call_tool=AsyncMock(),
    )
    payload = {
        "header": {
            "event_id": "event-http-1",
            "event_type": "im.message.receive_v1",
            "token": "verify-me",
        },
        "event": {
            "sender": {"sender_id": {"open_id": "ou-user"}},
            "message": {
                "message_id": "message-http-1",
                "chat_id": "chat-http-1",
                "message_type": "text",
                "content": '{"text":"规划杭州一日游"}',
            },
        },
    }

    with TestClient(app) as lifespan_client:
        app.state.agent_runtime = runtime
        app.state.mcp_manager = manager
        app.state.outbox = None
        app.state.outbox_worker = None
        response = lifespan_client.post("/webhooks/feishu", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "thread_id": "feishu:chat-http-1",
    }
    runtime.chat.assert_awaited_once()
    manager.call_tool.assert_awaited_once_with(
        "lark_openapi.im_v1_message_create",
        {
            "data": {
                "receive_id": "chat-http-1",
                "msg_type": "text",
                "content": '{"text": "规划已生成"}',
                "uuid": "travelmind-message-http-1",
            },
            "params": {"receive_id_type": "chat_id"},
        },
    )
    del app.state.agent_runtime


@pytest.mark.anyio
async def test_feishu_message_can_approve_pending_tool() -> None:
    runtime = Mock(spec=TravelAgentRuntime)
    runtime.pending_approvals = AsyncMock(return_value=[{"tool": "calendar.create"}])
    runtime.resume = AsyncMock(
        return_value=AgentRunResult(status="completed", message="日历已经创建")
    )
    manager = SimpleNamespace(
        tools={"lark_openapi.im_v1_message_create": object()},
        call_tool=AsyncMock(),
    )
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(agent_runtime=runtime, mcp_manager=manager)
        )
    )

    await _run_feishu_agent(
        request,
        "批准",
        "feishu:user-1",
        "feishu:chat-1",
        "chat-1",
        "message-1",
    )

    runtime.resume.assert_awaited_once_with(
        "feishu:chat-1",
        True,
        AgentContext(
            user_id="feishu:user-1",
            thread_id="feishu:chat-1",
            channel="feishu",
        ),
    )
    manager.call_tool.assert_awaited_once()
