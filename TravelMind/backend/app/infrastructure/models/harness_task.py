"""SQLAlchemy mapping for durable single-Agent Harness tasks."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class HarnessTaskRecord(Base):
    """A dependency-aware task that survives process restarts."""

    __tablename__ = "harness_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    blocked_by: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False, default="travel_agent")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
