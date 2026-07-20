"""Register, validate, and dispatch local and MCP tools through one catalog."""

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.harness.permissions import RiskLevel

ToolHandler = Callable[..., Any | Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Metadata and executable handler for one Harness tool."""

    name: str
    description: str
    args_model: type[BaseModel]
    handler: ToolHandler
    source: str = "local"
    risk_level: RiskLevel = RiskLevel.READ


class ToolRegistry:
    """Keep tool names unique and validate every invocation."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a uniquely named tool."""
        if tool.name in self._tools:
            raise ValueError(f"工具已注册：{tool.name}")
        if "." not in tool.name:
            raise ValueError("工具名称必须使用 namespace.action 格式")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        """Return a tool or raise a clear lookup error."""
        try:
            return self._tools[name]
        except KeyError as error:
            raise KeyError(f"未知工具：{name}") from error

    def list_tools(self) -> list[ToolDefinition]:
        """Return tools sorted by stable name."""
        return [self._tools[name] for name in sorted(self._tools)]

    async def invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        """Validate arguments and execute a synchronous or asynchronous handler."""
        tool = self.get(name)
        validated = tool.args_model.model_validate(arguments)
        values = {
            field_name: getattr(validated, field_name)
            for field_name in validated.__class__.model_fields
        }
        result = tool.handler(**values)
        if inspect.isawaitable(result):
            return await result
        return result
