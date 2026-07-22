"""SQLAlchemy mapping for the MySQL ``itinerary_items`` table."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class ItineraryItem(Base):
    """Store one ordered activity belonging to a trip."""

    __tablename__ = "itinerary_items"
    __table_args__ = {"comment": "行程日程项表"}

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="日程项ID",
    )
    trip_id: Mapped[int] = mapped_column(
        BigInteger,
        comment="所属行程ID（逻辑外键）",
    )
    day_number: Mapped[int] = mapped_column(Integer, comment="行程第几天")
    sort_order: Mapped[int] = mapped_column(Integer, comment="当天排序序号")
    title: Mapped[str] = mapped_column(String(200), comment="日程标题")
    location: Mapped[str] = mapped_column(String(200), comment="地点")
    start_at: Mapped[datetime | None] = mapped_column(DateTime, comment="开始时间")
    end_at: Mapped[datetime | None] = mapped_column(DateTime, comment="结束时间")
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        server_default=text("0"),
        comment="预计费用",
    )
    source: Mapped[str | None] = mapped_column(String(100), comment="数据来源")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="创建时间",
    )
