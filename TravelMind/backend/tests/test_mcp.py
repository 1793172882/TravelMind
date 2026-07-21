"""Tests for MCP configuration and tool adaptation without network access."""

from types import SimpleNamespace
import sys
from typing import Any

import pytest

from app.harness.tool_registry import ToolRegistry
from app.mcp.config import MCPConfig
from app.mcp.manager import DiscoveredMCPTool
from app.mcp.manager import MCPManager
from app.mcp.tool_adapter import model_from_json_schema, register_mcp_tools
from app.mcp.tool_adapter import _risk_level
from app.harness.permissions import RiskLevel


def test_mcp_config_and_json_schema() -> None:
    config = MCPConfig.model_validate(
        {
            "servers": {
                "demo": {
                    "enabled": False,
                    "transport": "stdio",
                    "command": "python",
                }
            }
        }
    )
    arguments = model_from_json_schema(
        "EchoArguments",
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    )

    assert config.servers["demo"].enabled is False
    assert arguments(text="ok").text == "ok"


def test_stdio_config_maps_secrets_from_named_settings() -> None:
    config = MCPConfig.model_validate(
        {
            "servers": {
                "lark": {
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@larksuiteoapi/lark-mcp@0.5.1", "mcp"],
                    "env_from": {
                        "APP_ID": "FEISHU_APP_ID",
                        "APP_SECRET": "FEISHU_APP_SECRET",
                    },
                }
            }
        }
    )

    server = config.servers["lark"]
    assert server.args[-1] == "mcp"
    assert server.env_from["APP_SECRET"] == "FEISHU_APP_SECRET"


def test_lark_write_tools_require_harness_approval() -> None:
    for name in (
        "im_v1_message_create",
        "docx_v1_document_create",
        "docx_v1_documentBlockDescendant_create",
        "calendar_v4_calendarEvent_create",
    ):
        assert _risk_level(name) is RiskLevel.WRITE


class FakeManager:
    def __init__(self) -> None:
        self.tools = {
            "demo.echo": DiscoveredMCPTool(
                server="demo",
                name="echo",
                description="Echo text",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            )
        }

    async def call_tool(self, qualified_name: str, arguments: dict[str, Any]) -> Any:
        return SimpleNamespace(structuredContent={"qualified_name": qualified_name, **arguments})


@pytest.mark.anyio
async def test_mcp_tool_is_registered_and_invoked() -> None:
    registry = ToolRegistry()
    register_mcp_tools(FakeManager(), registry)  # type: ignore[arg-type]

    result = await registry.invoke("demo.echo", {"text": "hello"})

    assert result == {"qualified_name": "demo.echo", "text": "hello"}


@pytest.mark.anyio
async def test_official_stdio_mcp_lifecycle() -> None:
    manager = MCPManager(
        MCPConfig.model_validate(
            {
                "servers": {
                    "demo": {
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": ["-m", "tests.fake_mcp_server"],
                    }
                }
            }
        )
    )

    await manager.start()
    try:
        assert manager.errors == {}
        assert "demo.echo" in manager.tools
        result = await manager.call_tool("demo.echo", {"text": "hello"})
        assert result.isError is False
    finally:
        await manager.close()
