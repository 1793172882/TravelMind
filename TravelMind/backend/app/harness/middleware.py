"""Permission and recovery pipeline wrapped around every Harness tool."""

from typing import Any

from langgraph.types import interrupt

from app.harness.permissions import PermissionDecision, PermissionEngine
from app.harness.recovery import retry_async
from app.harness.tool_registry import ToolRegistry


class ApprovalRequired(RuntimeError):
    """Signal that a tool call must pause for human approval."""


class ToolPermissionDenied(RuntimeError):
    """Signal that the Harness policy rejected a tool call."""


class ToolExecutor:
    """Execute registered tools through one permission and recovery pipeline."""

    def __init__(
        self,
        registry: ToolRegistry,
        permissions: PermissionEngine | None = None,
    ) -> None:
        self.registry = registry
        self.permissions = permissions or PermissionEngine()

    async def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        approved: bool = False,
    ) -> Any:
        """Check policy, validate arguments, and retry only transient failures."""
        tool = self.registry.get(name)
        decision = self.permissions.decide(tool.risk_level, approved)
        if decision is PermissionDecision.ASK:
            approved = bool(
                interrupt(
                    {
                        "type": "tool_approval",
                        "tool": name,
                        "arguments": arguments,
                    }
                )
            )
            if not approved:
                return {"status": "rejected", "tool": name}
        if decision is PermissionDecision.DENY:
            raise ToolPermissionDenied(f"工具已被拒绝：{name}")
        return await retry_async(lambda: self.registry.invoke(name, arguments))
