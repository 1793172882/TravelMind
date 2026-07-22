"""Pydantic schemas shared by Agent structured output, API, and constraint checks."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TripRequirement(BaseModel):
    destination: str
    start_at: datetime
    end_at: datetime
    budget: Decimal | None = Field(default=None, ge=0)
    max_walking_distance_m: int | None = Field(default=None, ge=0)
    must_visit: list[str] = Field(default_factory=list)


class ItineraryItem(BaseModel):
    title: str
    location: str
    start_at: datetime
    end_at: datetime
    estimated_cost: Decimal = Field(default=Decimal("0"), ge=0)
    walking_distance_m: int = Field(default=0, ge=0)
    source: str | None = None


class Itinerary(BaseModel):
    items: list[ItineraryItem]

