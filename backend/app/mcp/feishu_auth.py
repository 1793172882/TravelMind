"""Automatic tenant authentication for Feishu's official remote MCP."""

import asyncio
from time import monotonic
from typing import Any

import httpx

FEISHU_TENANT_TOKEN_URL = (
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
)


class FeishuAuthError(RuntimeError):
    """Raised without exposing credentials or access tokens."""


class FeishuTenantTokenProvider:
    """Fetch and cache a short-lived tenant_access_token."""

    def __init__(self, app_id: str, app_secret: str, client: httpx.AsyncClient) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.client = client
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        if self._token and monotonic() < self._expires_at:
            return self._token
        async with self._lock:
            if self._token and monotonic() < self._expires_at:
                return self._token
            response = await self.client.post(
                FEISHU_TENANT_TOKEN_URL,
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            response.raise_for_status()
            try:
                payload: dict[str, Any] = response.json()
            except ValueError as error:
                raise FeishuAuthError("飞书认证服务返回了无效 JSON") from error
            token = payload.get("tenant_access_token")
            if payload.get("code") != 0 or not isinstance(token, str) or not token:
                message = payload.get("msg") or "unknown error"
                raise FeishuAuthError(f"飞书 tenant_access_token 获取失败：{message}")
            expires_in = int(payload.get("expire") or 7200)
            self._token = token
            self._expires_at = monotonic() + max(expires_in - 60, 1)
            return token


class FeishuTenantAuth(httpx.Auth):
    """Attach Feishu's MCP-specific tenant token header to every request."""

    def __init__(
        self,
        provider: FeishuTenantTokenProvider,
        allowed_tools: list[str] | None = None,
    ) -> None:
        self.provider = provider
        self.allowed_tools = allowed_tools or []

    async def async_auth_flow(self, request: httpx.Request):  # type: ignore[no-untyped-def]
        request.headers["X-Lark-MCP-TAT"] = await self.provider.get_token()
        if self.allowed_tools:
            request.headers["X-Lark-MCP-Allowed-Tools"] = ",".join(self.allowed_tools)
        yield request
