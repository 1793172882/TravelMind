"""Current Agent identity shared with Harness tools during one run."""

from contextvars import ContextVar

from app.agent.state import AgentContext


current_agent_context: ContextVar[AgentContext | None] = ContextVar(
    "current_agent_context", default=None
)


def require_agent_context() -> AgentContext:
    """Return the active context or fail outside an Agent invocation."""
    context = current_agent_context.get()
    if context is None:
        raise RuntimeError("该工具只能由 Agent 调用")
    return context
