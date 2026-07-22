"""Typed runtime context and persistent Agent state definitions."""

from dataclasses import dataclass
from typing import Any, TypedDict


@dataclass(frozen=True, slots=True)
class AgentContext:
    user_id: str
    thread_id: str
    channel: str = "web"
    agent_id: str = "travel_agent"


class TravelAgentState(TypedDict, total=False):
    messages: list[Any]
    trip_id: str
    trip_version: int
    requirements: dict[str, Any]
    todo_items: list[dict[str, Any]]
    candidate_itinerary: dict[str, Any]
    validation_errors: list[str]
    pending_approval: dict[str, Any]
    sync_status: dict[str, str]

