"""SQLAlchemy mapping for durable webhook idempotency."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class WebhookEventRecord(Base):
    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
