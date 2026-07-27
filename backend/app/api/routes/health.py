from fastapi import APIRouter, Request

from app.config import settings

router = APIRouter(tags=["operations"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "TravelMind"}

@router.get("/version")
def version() -> dict[str, str]:
    return {"name": "TravelMind","version": "0.1.0"}


@router.get("/metrics")
def metrics(request: Request) -> dict:
    events = getattr(request.app.state, "events", None)
    return {
        "http": dict(getattr(request.app.state, "http_metrics", {})),
        "agent_events": events.metrics() if events else {},
    }


@router.get("/integrations")
def integrations(request: Request) -> dict:
    manager = getattr(request.app.state, "mcp_manager", None)
    tools = list(getattr(manager, "tools", {}))
    return {
        "qwen_configured": bool(settings.model_api_key or settings.dashscope_api_key),
        "amap_configured": settings.amap_api_key is not None,
        "rag_configured": getattr(request.app.state, "knowledge_store", None) is not None,
        "feishu_app_configured": bool(settings.feishu_app_id and settings.feishu_app_secret),
        "mcp_servers": list(getattr(manager, "sessions", {})),
        "mcp_tools": tools,
        "mcp_errors": getattr(manager, "errors", {}),
        "feishu_write_ready": "lark_openapi.im_v1_message_create" in tools,
    }
