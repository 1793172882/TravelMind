"""Human approval lookup and LangGraph resume endpoints."""

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.state import AgentContext
from app.api.dependencies import AgentRuntimeDependency
from app.api.schemas.chat import ChatResponse

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalResponse(BaseModel):
    """Current approval payloads for one thread."""

    thread_id: str
    pending: list[Any] = Field(default_factory=list)


class ApprovalDecisionRequest(BaseModel):
    """Decision and context required to resume a thread."""

    decision: Literal["approve", "reject"]
    user_id: str = "anonymous"
    channel: str = "web"


@router.get("/{thread_id}", response_model=ApprovalResponse)
async def get_approvals(
    thread_id: str,
    runtime: AgentRuntimeDependency,
) -> ApprovalResponse:
    """Return pending approval payloads without resuming execution."""
    return ApprovalResponse(
        thread_id=thread_id,
        pending=await runtime.pending_approvals(thread_id),
    )


@router.post("/{thread_id}", response_model=ChatResponse)
async def decide_approval(
    thread_id: str,
    request: ApprovalDecisionRequest,
    runtime: AgentRuntimeDependency,
) -> ChatResponse:
    """Approve or reject the current interrupt and resume the same thread."""
    result = await runtime.resume(
        thread_id,
        request.decision == "approve",
        AgentContext(
            user_id=request.user_id,
            thread_id=thread_id,
            channel=request.channel,
        ),
    )
    return ChatResponse(
        thread_id=thread_id,
        message=result.message,
        status=result.status,
        pending_approvals=result.pending_approvals,
    )
