"""Business operations for creating and querying trips."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.models.itinerary_item import ItineraryItem
from app.infrastructure.models.trip import Trip
from app.infrastructure.repositories.itinerary_item import ItineraryItemRepository
from app.infrastructure.repositories.trip import TripRepository


class TripService:
    """Coordinate trip business operations and transaction boundaries."""

    def __init__(self, session: Session) -> None:
        """Use one session and repository for the current operation."""
        self.session = session
        self.repository = TripRepository(session)
        self.itinerary_items = ItineraryItemRepository(session)

    def create_trip(
        self,
        *,
        origin: str,
        destination: str,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        budget: Decimal | None = None,
    ) -> Trip:
        """Create a trip and commit it as one transaction."""
        trip = Trip(
            origin=origin,
            destination=destination,
            start_at=start_at,
            end_at=end_at,
            budget=budget,
        )
        self.repository.add(trip)
        self._commit()
        self.session.refresh(trip)
        return trip

    def create_trip_with_items(
        self,
        *,
        origin: str,
        destination: str,
        start_at: datetime,
        end_at: datetime,
        budget: Decimal | None,
        items: Sequence[dict[str, Any]],
    ) -> tuple[Trip, list[ItineraryItem]]:
        """Persist a complete itinerary atomically."""
        trip = Trip(
            origin=origin,
            destination=destination,
            start_at=start_at,
            end_at=end_at,
            budget=budget,
        )
        self.repository.add(trip)
        self.session.flush()
        stored_items = [ItineraryItem(trip_id=trip.id, **item) for item in items]
        self.itinerary_items.add_all(stored_items)
        self._commit()
        self.session.refresh(trip)
        return trip, stored_items

    def get_trip(self, trip_id: int) -> Trip | None:
        """Return one trip by ID, or None when it does not exist."""
        return self.repository.get_by_id(trip_id)

    def list_trips(self) -> Sequence[Trip]:
        """Return all stored trips."""
        return self.repository.list_all()

    def archive_trip(self, trip_id: int) -> Trip | None:
        """Mark a stored trip as archived."""
        trip = self.repository.get_by_id(trip_id)
        if trip is None:
            return None
        trip.status = "archived"
        self._commit()
        self.session.refresh(trip)
        return trip

    def add_itinerary_item(
        self,
        *,
        trip_id: int,
        day_number: int,
        sort_order: int,
        title: str,
        location: str,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        estimated_cost: Decimal = Decimal("0"),
        source: str | None = None,
    ) -> ItineraryItem | None:
        """Add an itinerary item after validating the logical trip reference."""
        if self.repository.get_by_id(trip_id) is None:
            return None
        item = ItineraryItem(
            trip_id=trip_id,
            day_number=day_number,
            sort_order=sort_order,
            title=title,
            location=location,
            start_at=start_at,
            end_at=end_at,
            estimated_cost=estimated_cost,
            source=source,
        )
        self.itinerary_items.add(item)
        self._commit()
        self.session.refresh(item)
        return item

    def list_itinerary_items(self, trip_id: int) -> Sequence[ItineraryItem] | None:
        """Return ordered itinerary items, or None when the trip is absent."""
        if self.repository.get_by_id(trip_id) is None:
            return None
        return self.itinerary_items.list_by_trip_id(trip_id)

    def _commit(self) -> None:
        """Commit the current transaction and restore the session on failure."""
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
