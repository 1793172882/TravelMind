from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dependencies import get_agent_runtime, get_trip_service
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
    runtime = Mock(spec=TravelAgentRuntime)
    runtime.chat = AsyncMock(
        return_value=AgentRunResult(status="completed", message="规划已生成")
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
        response = lifespan_client.post("/webhooks/feishu", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "thread_id": "feishu:chat-http-1",
    }
    runtime.chat.assert_awaited_once()
    del app.state.agent_runtime
