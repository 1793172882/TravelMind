"""Own one official MCP ClientSession per configured Server."""

import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from app.mcp.config import MCPConfig, MCPServerConfig
from app.config import settings
from app.mcp.feishu_auth import FeishuTenantAuth, FeishuTenantTokenProvider


@dataclass(frozen=True, slots=True)
class DiscoveredMCPTool:
    """Remote MCP tool metadata retained for Harness registration."""

    server: str
    name: str
    description: str
    input_schema: dict[str, Any]

    @property
    def qualified_name(self) -> str:
        return f"{self.server}.{self.name}"


class MCPManager:
    """Connect, discover, invoke, and close independent MCP sessions."""

    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        self.sessions: dict[str, ClientSession] = {}
        self.tools: dict[str, DiscoveredMCPTool] = {}
        self.errors: dict[str, str] = {}
        self._stacks: dict[str, AsyncExitStack] = {}

    async def start(self) -> None:
        """Connect enabled servers; isolate failures to one server."""
        for name, server in self.config.servers.items():
            if not server.enabled:
                continue
            try:
                await self._connect(name, server)
            except Exception as error:
                self.errors[name] = str(error)

    async def _connect(self, name: str, server: MCPServerConfig) -> None:
        stack = AsyncExitStack()
        try:
            if server.transport == "stdio":
                parameters = StdioServerParameters(
                    command=server.command or "",
                    args=server.args,
                )
                read, write = await stack.enter_async_context(stdio_client(parameters))
            else:
                url = self._environment_value(server.url_env or "")
                headers: dict[str, str] = {}
                auth: httpx.Auth | None = None
                if server.auth == "feishu_tenant":
                    if settings.feishu_app_id is None or settings.feishu_app_secret is None:
                        raise RuntimeError("缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET")
                    token_client = await stack.enter_async_context(httpx.AsyncClient())
                    provider = FeishuTenantTokenProvider(
                        settings.feishu_app_id,
                        settings.feishu_app_secret.get_secret_value(),
                        token_client,
                    )
                    auth = FeishuTenantAuth(provider, server.allowed_tools)
                elif server.token_env:
                    headers["Authorization"] = (
                        f"Bearer {self._environment_value(server.token_env)}"
                    )
                http_client = await stack.enter_async_context(
                    httpx.AsyncClient(headers=headers, auth=auth, follow_redirects=True)
                )
                streams = await stack.enter_async_context(
                    streamable_http_client(url, http_client=http_client)
                )
                read, write = streams[0], streams[1]

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            listed = await session.list_tools()
        except Exception:
            await stack.aclose()
            raise

        self._stacks[name] = stack
        self.sessions[name] = session
        for tool in listed.tools:
            discovered = DiscoveredMCPTool(
                server=name,
                name=tool.name,
                description=tool.description or tool.name,
                input_schema=tool.inputSchema,
            )
            self.tools[discovered.qualified_name] = discovered

    @staticmethod
    def _environment_value(name: str) -> str:
        """Resolve known .env settings before falling back to process variables."""
        configured = {
            "FEISHU_MCP_URL": settings.feishu_mcp_url,
            "FEISHU_MCP_TOKEN": (
                settings.feishu_mcp_token.get_secret_value()
                if settings.feishu_mcp_token
                else None
            ),
        }.get(name)
        if configured:
            return configured
        return os.environ[name]

    async def call_tool(self, qualified_name: str, arguments: dict[str, Any]) -> Any:
        """Call one discovered tool through its owning session."""
        tool = self.tools[qualified_name]
        return await self.sessions[tool.server].call_tool(tool.name, arguments)

    async def close(self) -> None:
        """Close every session and transport in reverse connection order."""
        for name in reversed(list(self._stacks)):
            await self._stacks[name].aclose()
        self._stacks.clear()
        self.sessions.clear()
        self.tools.clear()
