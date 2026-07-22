"""Database operations for the ``trips`` table."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models.trip import Trip


class TripRepository:
    """Add and query trip records without controlling transactions."""

    def __init__(self, session: Session) -> None:
        """Bind this repository to the current request's session."""
        self.session = session

    def add(self, trip: Trip) -> None:
        """Add a trip to the current transaction."""
        self.session.add(trip)

    def get_by_id(self, trip_id: int, owner_id: str) -> Trip | None:
        """Query a trip by primary key; return None when absent."""
        statement = select(Trip).where(Trip.id == trip_id, Trip.owner_id == owner_id)
        return self.session.scalar(statement)

    def list_all(self, owner_id: str) -> Sequence[Trip]:
        """Return trips from newest to oldest."""
        statement = (
            select(Trip)
            .where(Trip.owner_id == owner_id)
            .order_by(Trip.created_at.desc(), Trip.id.desc())
        )
        return self.session.scalars(statement).all()

    def delete(self, trip: Trip) -> None:
        self.session.delete(trip)
