"""SQLAlchemy mapping for durable pre-trip automation jobs."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class ScheduledJobRecord(Base):
    __tablename__ = "scheduled_jobs"
    __table_args__ = (UniqueConstraint("trip_id", "kind", name="uk_scheduled_trip_kind"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
