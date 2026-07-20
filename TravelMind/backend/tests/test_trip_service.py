"""Unit tests for TripService business and transaction handling."""

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
