"""SQLAlchemy mapping for the MySQL ``trips`` table."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, FetchedValue, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Trip(Base):
    """Store the basic information and current state of a trip."""

    __tablename__ = "trips"
    __table_args__ = {"comment": "行程主表"}

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="行程ID",
    )
    owner_id: Mapped[str] = mapped_column(
        String(200), nullable=False, default="anonymous", comment="逻辑用户标识"
    )
    thread_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="创建行程的 Agent 会话"
    )
    origin: Mapped[str] = mapped_column(String(100), comment="出发地")
    destination: Mapped[str] = mapped_column(String(100), comment="目的地")
    start_at: Mapped[datetime | None] = mapped_column(DateTime, comment="行程开始时间")
    end_at: Mapped[datetime | None] = mapped_column(DateTime, comment="行程结束时间")
    budget: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), comment="行程预算")
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'draft'"),
        comment="行程状态",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=FetchedValue(),
        comment="更新时间",
    )
