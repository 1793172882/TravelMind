"""Compose FastAPI dependencies without leaking infrastructure into controllers."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.agent.runtime import TravelAgentRuntime, build_agent_runtime
from app.infrastructure.database import get_db
from app.services.trip import TripService

DatabaseSession = Annotated[Session, Depends(get_db)]


def get_trip_service(session: DatabaseSession) -> TripService:
    """Build a trip service for the current request's database session."""
    return TripService(session)


TripServiceDependency = Annotated[TripService, Depends(get_trip_service)]


def resolve_agent_runtime(request: Request) -> TravelAgentRuntime:
    """Reuse one checkpointed runtime and the shared local/MCP tool registry."""
    runtime = getattr(request.app.state, "agent_runtime", None)
    if runtime is not None:
        return runtime
    registry = getattr(request.app.state, "tool_registry", None)
    checkpointer = getattr(request.app.state, "checkpointer", None)
    try:
        runtime = build_agent_runtime(registry=registry, checkpointer=checkpointer)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    request.app.state.agent_runtime = runtime
    return runtime


def get_agent_runtime(request: Request) -> TravelAgentRuntime:
    """FastAPI dependency wrapper for the shared Agent runtime."""
    return resolve_agent_runtime(request)


AgentRuntimeDependency = Annotated[TravelAgentRuntime, Depends(get_agent_runtime)]
