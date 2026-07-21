from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.agent.runtime import build_default_registry
from app.api.router import api_router
from app.channels.feishu import EventDeduplicator
from app.config import PROJECT_ROOT, settings
from app.infrastructure.checkpoint import TravelMindMySQLSaver
from app.mcp.config import MCPConfig
from app.mcp.manager import MCPManager
from app.mcp.tool_adapter import register_mcp_tools


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start optional MCP sessions and close them with the application."""
    registry = build_default_registry()
    manager = MCPManager(MCPConfig.load(settings.mcp_config_path))
    await manager.start()
    register_mcp_tools(manager, registry)
    checkpoint_context = TravelMindMySQLSaver.from_conn_string(
        settings.langgraph_database_url
    )
    checkpointer = await checkpoint_context.__aenter__()
    await checkpointer.setup()
    app.state.tool_registry = registry
    app.state.mcp_manager = manager
    app.state.checkpointer = checkpointer
    app.state.feishu_events = EventDeduplicator()
    try:
        yield
    finally:
        await manager.close()
        await checkpoint_context.__aexit__(None, None, None)


app = FastAPI(title="TravelMind", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)
app.mount(
    "/ui",
    StaticFiles(directory=PROJECT_ROOT / "frontend", html=True),
    name="ui",
)
