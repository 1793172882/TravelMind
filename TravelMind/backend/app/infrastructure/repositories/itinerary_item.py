"""Database operations for the ``itinerary_items`` table."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models.itinerary_item import ItineraryItem


class ItineraryItemRepository:
    """Add and query itinerary items without controlling transactions."""

    def __init__(self, session: Session) -> None:
        """Bind this repository to the current request's session."""
        self.session = session

    def add(self, item: ItineraryItem) -> None:
        """Add an itinerary item to the current transaction."""
        self.session.add(item)

    def add_all(self, items: Sequence[ItineraryItem]) -> None:
        """Add multiple itinerary items to the current transaction."""
        self.session.add_all(items)

    def list_by_trip_id(self, trip_id: int) -> Sequence[ItineraryItem]:
        """Return a trip's itinerary items in display order."""
        statement = (
            select(ItineraryItem)
            .where(ItineraryItem.trip_id == trip_id)
            .order_by(ItineraryItem.day_number, ItineraryItem.sort_order)
        )
        return self.session.scalars(statement).all()
