"""Agent chat, history and progress event endpoints."""

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agent.state import AgentContext
from app.api.dependencies import AgentRuntimeDependency, CurrentUserDependency
from app.api.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/{thread_id}/history", response_model=list[dict[str, str]])
async def chat_history(
    thread_id: str,
    runtime: AgentRuntimeDependency,
    user: CurrentUserDependency,
) -> list[dict[str, str]]:
    """Restore visible conversation messages from the LangGraph checkpoint."""
    return await runtime.history(user.thread_id(thread_id))


@router.get("/{thread_id}/events")
async def chat_events(
    thread_id: str,
    request: Request,
    user: CurrentUserDependency,
    last_event_id: Annotated[int | None, Header()] = None,
) -> StreamingResponse:
    """Stream transient Agent and tool progress as standard SSE frames."""
    broker = request.app.state.events

    async def stream() -> AsyncIterator[str]:
        async for event in broker.subscribe(user.thread_id(thread_id), last_event_id or 0):
            payload = json.dumps(
                {"type": event.type, "data": event.data, "created_at": event.created_at},
                ensure_ascii=False,
            )
            yield f"id: {event.id}\nevent: {event.type}\ndata: {payload}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    runtime: AgentRuntimeDependency,
    user: CurrentUserDependency,
) -> ChatResponse:
    """Run one checkpointed Agent turn."""
    context = AgentContext(
        user_id=user.user_id,
        thread_id=user.thread_id(request.thread_id),
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
