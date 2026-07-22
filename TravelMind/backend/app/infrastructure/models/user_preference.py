"""SQLAlchemy mapping for durable Agent user preferences."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class UserPreferenceRecord(Base):
    """One merged preference record per channel user."""

    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(String(200), primary_key=True, comment="用户标识")
    max_walking_distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_transport: Mapped[list[str]] = mapped_column(JSON, default=list)
    dietary_restrictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    travels_with_elderly: Mapped[bool | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
