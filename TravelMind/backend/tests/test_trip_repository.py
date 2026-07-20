"""Unit tests for TripRepository database operations."""

from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.infrastructure.models.trip import Trip
from app.infrastructure.repositories.trip import TripRepository


def test_add_trip_uses_current_session() -> None:
    session = Mock(spec=Session)
    trip = Trip(origin="北京", destination="上海")

    TripRepository(session).add(trip)

    session.add.assert_called_once_with(trip)


def test_get_trip_by_id() -> None:
    session = Mock(spec=Session)
    trip = Trip(origin="北京", destination="上海")
    session.get.return_value = trip

    result = TripRepository(session).get_by_id(1001)

    assert result is trip
    session.get.assert_called_once_with(Trip, 1001)
