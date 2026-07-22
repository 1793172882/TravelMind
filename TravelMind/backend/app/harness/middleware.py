"""Permission and recovery pipeline wrapped around every Harness tool."""

from typing import Any

from langgraph.types import interrupt

from app.harness.permissions import PermissionDecision, PermissionEngine, RiskLevel
from app.harness.recovery import retry_async
from app.harness.events import EventBroker
from app.harness.runtime_context import current_agent_context
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
        events: EventBroker | None = None,
    ) -> None:
        self.registry = registry
        self.permissions = permissions or PermissionEngine()
        self.events = events

    async def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        approved: bool = False,
    ) -> Any:
        """Check policy, validate arguments, and retry only transient failures."""
        tool = self.registry.get(name)
        context = current_agent_context.get()
        if self.events and context:
            await self.events.publish(context.thread_id, "tool.started", tool=name)
        decision = self.permissions.decide(tool.risk_level, approved)
        if decision is PermissionDecision.ASK:
            if self.events and context:
                await self.events.publish(
                    context.thread_id,
                    "approval.required",
                    tool=name,
                    arguments=arguments,
                )
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
                if self.events and context:
                    await self.events.publish(context.thread_id, "tool.rejected", tool=name)
                return {"status": "rejected", "tool": name}
        if decision is PermissionDecision.DENY:
            raise ToolPermissionDenied(f"工具已被拒绝：{name}")
        try:
            result = await retry_async(
                lambda: self.registry.invoke(name, arguments),
                attempts=1 if tool.risk_level is RiskLevel.WRITE else 2,
            )
        except Exception as error:
            if self.events and context:
                await self.events.publish(
                    context.thread_id,
                    "tool.failed",
                    tool=name,
                    error=type(error).__name__,
                )
            raise
        if self.events and context:
            await self.events.publish(context.thread_id, "tool.completed", tool=name)
        return result
