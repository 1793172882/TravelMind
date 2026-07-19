"""SQLAlchemy ORM models for TravelMind database tables."""

from app.infrastructure.models.itinerary_item import ItineraryItem
from app.infrastructure.models.trip import Trip

__all__ = ["ItineraryItem", "Trip"]
