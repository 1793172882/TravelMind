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
from app.harness.scheduler import cancel_trip_weather_checks, schedule_trip_weather_checks


class TripService:
    """Coordinate trip business operations and transaction boundaries."""

    def __init__(
        self,
        session: Session,
        *,
        owner_id: str = "anonymous",
        thread_id: str | None = None,
    ) -> None:
        """Use one session and repository for the current operation."""
        self.session = session
        self.owner_id = owner_id
        self.thread_id = thread_id
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
        thread_id: str | None = None,
    ) -> Trip:
        """Create a trip and commit it as one transaction."""
        trip = Trip(
            owner_id=self.owner_id,
            thread_id=thread_id or self.thread_id,
            origin=origin,
            destination=destination,
            start_at=start_at,
            end_at=end_at,
            budget=budget,
        )
        self.repository.add(trip)
        self.session.flush()
        schedule_trip_weather_checks(self.session, trip)
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
            owner_id=self.owner_id,
            thread_id=self.thread_id,
            origin=origin,
            destination=destination,
            start_at=start_at,
            end_at=end_at,
            budget=budget,
        )
        self.repository.add(trip)
        self.session.flush()
        schedule_trip_weather_checks(self.session, trip)
        stored_items = [ItineraryItem(trip_id=trip.id, **item) for item in items]
        self.itinerary_items.add_all(stored_items)
        self._commit()
        self.session.refresh(trip)
        return trip, stored_items

    def get_trip(self, trip_id: int) -> Trip | None:
        """Return one trip by ID, or None when it does not exist."""
        return self.repository.get_by_id(trip_id, self.owner_id)

    def list_trips(self) -> Sequence[Trip]:
        """Return all stored trips."""
        return self.repository.list_all(self.owner_id)

    def archive_trip(self, trip_id: int) -> Trip | None:
        """Mark a stored trip as archived."""
        trip = self.repository.get_by_id(trip_id, self.owner_id)
        if trip is None:
            return None
        trip.status = "archived"
        cancel_trip_weather_checks(self.session, trip_id)
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
        if self.repository.get_by_id(trip_id, self.owner_id) is None:
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
        if self.repository.get_by_id(trip_id, self.owner_id) is None:
            return None
        return self.itinerary_items.list_by_trip_id(trip_id)

    def update_trip(self, trip_id: int, **changes: Any) -> Trip | None:
        trip = self.repository.get_by_id(trip_id, self.owner_id)
        if trip is None:
            return None
        for field_name, value in changes.items():
            setattr(trip, field_name, value)
        if "start_at" in changes:
            schedule_trip_weather_checks(self.session, trip)
        self._commit()
        self.session.refresh(trip)
        return trip

    def delete_trip(self, trip_id: int) -> bool:
        trip = self.repository.get_by_id(trip_id, self.owner_id)
        if trip is None:
            return False
        cancel_trip_weather_checks(self.session, trip_id)
        self.itinerary_items.delete_by_trip_id(trip_id)
        self.repository.delete(trip)
        self._commit()
        return True

    def update_itinerary_item(
        self, trip_id: int, item_id: int, **changes: Any
    ) -> ItineraryItem | None:
        if self.repository.get_by_id(trip_id, self.owner_id) is None:
            return None
        item = self.itinerary_items.get_by_id(item_id, trip_id)
        if item is None:
            return None
        for field_name, value in changes.items():
            setattr(item, field_name, value)
        self._commit()
        self.session.refresh(item)
        return item

    def delete_itinerary_item(self, trip_id: int, item_id: int) -> bool:
        if self.repository.get_by_id(trip_id, self.owner_id) is None:
            return False
        item = self.itinerary_items.get_by_id(item_id, trip_id)
        if item is None:
            return False
        self.itinerary_items.delete(item)
        self._commit()
        return True

    def _commit(self) -> None:
        """Commit the current transaction and restore the session on failure."""
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
