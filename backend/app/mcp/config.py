"""Parse MCP server configuration without storing resolved credentials."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MCPServerConfig(BaseModel):
    """Connection metadata for one MCP Server."""

    enabled: bool = True
    transport: Literal["stdio", "streamable_http"]
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env_from: dict[str, str] = Field(default_factory=dict)
    url_env: str | None = None
    token_env: str | None = None
    auth: Literal["bearer", "feishu_tenant"] = "bearer"
    allowed_tools: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_transport_fields(self) -> "MCPServerConfig":
        """Require only the fields used by the selected transport."""
        if self.transport == "stdio" and not self.command:
            raise ValueError("stdio MCP Server 必须配置 command")
        if self.transport == "streamable_http" and not self.url_env:
            raise ValueError("streamable_http MCP Server 必须配置 url_env")
        return self


class MCPConfig(BaseModel):
    """Validated collection of named MCP Server configurations."""

    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "MCPConfig":
        """Load a JSON file, treating a missing optional file as no servers."""
        if not path.exists():
            return cls()
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
