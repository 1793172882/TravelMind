"""Agent chat HTTP endpoint."""

from fastapi import APIRouter, HTTPException

from app.agent.state import AgentContext
from app.api.dependencies import AgentRuntimeDependency
from app.api.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, runtime: AgentRuntimeDependency) -> ChatResponse:
    """Run one checkpointed Agent turn."""
    context = AgentContext(
        user_id=request.user_id,
        thread_id=request.thread_id,
        channel=request.channel,
    )
    try:
        result = await runtime.chat(request.message, context)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return ChatResponse(
        thread_id=request.thread_id,
        message=result.message,
        status=result.status,
        pending_approvals=result.pending_approvals,
    )
