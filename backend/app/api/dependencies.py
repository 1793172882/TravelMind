"""Compose FastAPI dependencies without leaking infrastructure into controllers."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.agent.runtime import TravelAgentRuntime, build_agent_runtime
from app.config import settings
from app.infrastructure.database import get_db
from app.services.trip import TripService
from app.services.knowledge import KnowledgeService
from app.services.auth import ANONYMOUS_USER, AuthenticationError, UserIdentity, parse_token

DatabaseSession = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> UserIdentity:
    if credentials is None:
        if settings.auth_required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="请先登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return ANONYMOUS_USER
    try:
        return parse_token(credentials.credentials)
    except (AuthenticationError, RuntimeError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


CurrentUserDependency = Annotated[UserIdentity, Depends(get_current_user)]


def get_trip_service(
    session: DatabaseSession,
    user: CurrentUserDependency,
) -> TripService:
    """Build a trip service for the current request's database session."""
    return TripService(session, owner_id=user.user_id)


TripServiceDependency = Annotated[TripService, Depends(get_trip_service)]


def get_knowledge_service(
    request: Request,
    session: DatabaseSession,
    user: CurrentUserDependency,
) -> KnowledgeService:
    """Build a user-scoped RAG service over the shared Chroma collection."""
    store = getattr(request.app.state, "knowledge_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="RAG 未配置，请检查 DASHSCOPE_API_KEY")
    return KnowledgeService(session, store, owner_id=user.user_id)


KnowledgeServiceDependency = Annotated[KnowledgeService, Depends(get_knowledge_service)]


def resolve_agent_runtime(request: Request) -> TravelAgentRuntime:
    """Reuse one checkpointed runtime and the shared local/MCP tool registry."""
    runtime = getattr(request.app.state, "agent_runtime", None)
    if runtime is not None:
        return runtime
    registry = getattr(request.app.state, "tool_registry", None)
    checkpointer = getattr(request.app.state, "checkpointer", None)
    memory_store = getattr(request.app.state, "memory_store", None)
    task_store = getattr(request.app.state, "task_store", None)
    skill_loader = getattr(request.app.state, "skill_loader", None)
    events = getattr(request.app.state, "events", None)
    try:
        runtime = build_agent_runtime(
            registry=registry,
            checkpointer=checkpointer,
            memory_store=memory_store,
            task_store=task_store,
            skill_loader=skill_loader,
            events=events,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    request.app.state.agent_runtime = runtime
    return runtime


def get_agent_runtime(request: Request) -> TravelAgentRuntime:
    """FastAPI dependency wrapper for the shared Agent runtime."""
    return resolve_agent_runtime(request)


AgentRuntimeDependency = Annotated[TravelAgentRuntime, Depends(get_agent_runtime)]
