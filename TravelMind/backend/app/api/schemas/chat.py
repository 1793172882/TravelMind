"""Pydantic schemas for Agent chat requests and responses."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """One user turn sent to the TravelMind Agent."""

    message: str = Field(min_length=1, max_length=10_000)
    thread_id: str = Field(min_length=1, max_length=100)
    user_id: str = Field(default="anonymous", min_length=1, max_length=100)
    channel: str = Field(default="web", min_length=1, max_length=30)


class ChatResponse(BaseModel):
    """Final Agent message for one turn."""

    thread_id: str
    message: str
    status: Literal["completed", "waiting_approval"]
    pending_approvals: list[Any] = Field(default_factory=list)
