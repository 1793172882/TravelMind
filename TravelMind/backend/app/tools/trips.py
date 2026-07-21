"""Agent tools that reach trip persistence only through ``TripService``."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.infrastructure.database import SessionLocal
from app.domain.constraints import validate_itinerary
from app.domain.models import Itinerary, TripRequirement
from app.services.trip import TripService


class CreateTripArgs(BaseModel):
    """Arguments for creating a draft trip."""

    origin: str = Field(min_length=1, max_length=100)
    destination: str = Field(min_length=1, max_length=100)
    start_at: datetime | None = None
    end_at: datetime | None = None
    budget: Decimal | None = Field(default=None, ge=0)


class TripIdArgs(BaseModel):
    """Arguments for reading one stored trip."""

    trip_id: int = Field(gt=0)


class AddItineraryItemArgs(TripIdArgs):
    """Arguments for appending one activity to a draft trip."""

    day_number: int = Field(ge=1)
    sort_order: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=200)
    start_at: datetime | None = None
    end_at: datetime | None = None
    estimated_cost: Decimal = Field(default=Decimal("0"), ge=0)
    source: str | None = Field(default=None, max_length=100)


class SaveItineraryArgs(BaseModel):
    """A complete candidate plan saved only after deterministic validation."""

    origin: str = Field(min_length=1, max_length=100)
    requirement: TripRequirement
    itinerary: Itinerary


def _trip_result(trip: Any) -> dict[str, Any]:
    return {
        "id": trip.id,
        "origin": trip.origin,
        "destination": trip.destination,
        "start_at": trip.start_at.isoformat() if trip.start_at else None,
        "end_at": trip.end_at.isoformat() if trip.end_at else None,
        "budget": str(trip.budget) if trip.budget is not None else None,
        "status": trip.status,
    }


def create_trip_record(**arguments: Any) -> dict[str, Any]:
    """Create a draft trip through the application service."""
    with SessionLocal() as session:
        trip = TripService(session).create_trip(**arguments)
        return _trip_result(trip)


def get_trip_record(trip_id: int) -> dict[str, Any]:
    """Read a trip and its ordered itinerary through the application service."""
    with SessionLocal() as session:
        service = TripService(session)
        trip = service.get_trip(trip_id)
        if trip is None:
            return {"status": "not_found", "trip_id": trip_id}
        items = service.list_itinerary_items(trip_id) or []
        result = _trip_result(trip)
        result["items"] = [
            {
                "id": item.id,
                "day_number": item.day_number,
                "sort_order": item.sort_order,
                "title": item.title,
                "location": item.location,
                "start_at": item.start_at.isoformat() if item.start_at else None,
                "end_at": item.end_at.isoformat() if item.end_at else None,
                "estimated_cost": str(item.estimated_cost),
                "source": item.source,
            }
            for item in items
        ]
        return result


def add_itinerary_item_record(**arguments: Any) -> dict[str, Any]:
    """Append an activity through the application service."""
    with SessionLocal() as session:
        item = TripService(session).add_itinerary_item(**arguments)
        if item is None:
            return {"status": "not_found", "trip_id": arguments["trip_id"]}
        return {
            "id": item.id,
            "trip_id": item.trip_id,
            "day_number": item.day_number,
            "sort_order": item.sort_order,
            "title": item.title,
            "location": item.location,
            "start_at": item.start_at.isoformat() if item.start_at else None,
            "end_at": item.end_at.isoformat() if item.end_at else None,
            "estimated_cost": str(item.estimated_cost),
            "source": item.source,
        }


def save_itinerary_record(
    origin: str,
    requirement: TripRequirement,
    itinerary: Itinerary,
) -> dict[str, Any]:
    """Validate and persist one complete itinerary in a single transaction."""
    errors = validate_itinerary(requirement, itinerary)
    if errors:
        return {"status": "invalid", "errors": errors}

    order_by_day: dict[int, int] = {}
    item_rows: list[dict[str, Any]] = []
    for item in sorted(itinerary.items, key=lambda value: value.start_at):
        day_number = (item.start_at.date() - requirement.start_at.date()).days + 1
        sort_order = order_by_day.get(day_number, 0)
        order_by_day[day_number] = sort_order + 1
        item_rows.append(
            {
                "day_number": day_number,
                "sort_order": sort_order,
                "title": item.title,
                "location": item.location,
                "start_at": item.start_at,
                "end_at": item.end_at,
                "estimated_cost": item.estimated_cost,
                "source": item.source,
            }
        )

    with SessionLocal() as session:
        trip, stored_items = TripService(session).create_trip_with_items(
            origin=origin,
            destination=requirement.destination,
            start_at=requirement.start_at,
            end_at=requirement.end_at,
            budget=requirement.budget,
            items=item_rows,
        )
        return {"status": "saved", "trip_id": trip.id, "item_count": len(stored_items)}
