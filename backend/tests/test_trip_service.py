"""Unit tests for TripService business and transaction handling."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.trip import TripService


def test_create_trip_commits_and_refreshes() -> None:
    session = Mock(spec=Session)

    trip = TripService(session).create_trip(
        origin="北京",
        destination="上海",
    )

    assert trip.origin == "北京"
    assert trip.destination == "上海"
    session.add.assert_called_once_with(trip)
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(trip)


def test_create_trip_rolls_back_when_commit_fails() -> None:
    session = Mock(spec=Session)
    session.commit.side_effect = SQLAlchemyError("commit failed")

    with pytest.raises(SQLAlchemyError):
        TripService(session).create_trip(
            origin="北京",
            destination="上海",
        )

    session.rollback.assert_called_once()


def test_create_trip_with_items_commits_once() -> None:
    session = Mock(spec=Session)
    session.flush.side_effect = lambda: None
    service = TripService(session)

    trip, items = service.create_trip_with_items(
        origin="上海",
        destination="杭州",
        start_at=datetime(2026, 8, 1, 9),
        end_at=datetime(2026, 8, 1, 18),
        budget=None,
        items=[
            {
                "day_number": 1,
                "sort_order": 0,
                "title": "游览西湖",
                "location": "西湖",
                "start_at": datetime(2026, 8, 1, 10),
                "end_at": datetime(2026, 8, 1, 12),
                "estimated_cost": 0,
                "source": "amap.poi",
            }
        ],
    )

    assert len(items) == 1
    assert items[0].trip_id == trip.id
    session.flush.assert_called_once()
    session.add_all.assert_called_once_with(items)
    session.commit.assert_called_once()
