"""Tests for Feishu's short-lived remote MCP authentication."""

import httpx
import pytest

from app.mcp.feishu_auth import FeishuTenantAuth, FeishuTenantTokenProvider


@pytest.mark.anyio
async def test_feishu_tenant_token_is_cached_and_sent_in_mcp_header() -> None:
    token_requests = 0

    def token_response(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests
        token_requests += 1
        return httpx.Response(
            200,
            json={"code": 0, "tenant_access_token": "tenant-token", "expire": 7200},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(token_response)) as token_client:
        provider = FeishuTenantTokenProvider("app-id", "app-secret", token_client)
        auth = FeishuTenantAuth(provider, ["docx.v1.document.rawContent"])

        def mcp_response(request: httpx.Request) -> httpx.Response:
            assert request.headers["X-Lark-MCP-TAT"] == "tenant-token"
            assert (
                request.headers["X-Lark-MCP-Allowed-Tools"]
                == "docx.v1.document.rawContent"
            )
            return httpx.Response(200, json={"ok": True})

        async with httpx.AsyncClient(
            auth=auth,
            transport=httpx.MockTransport(mcp_response),
        ) as mcp_client:
            await mcp_client.post("https://mcp.feishu.cn/mcp")
            await mcp_client.post("https://mcp.feishu.cn/mcp")

    assert token_requests == 1
