"""Pydantic schemas for trip HTTP requests and responses."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TripPreviewRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=50)
    destination: str = Field(min_length=1, max_length=50)


class TripPreviewResponse(BaseModel):
    message: str


class TripCreateRequest(BaseModel):
    """Data accepted when creating a trip."""

    origin: str = Field(min_length=1, max_length=100)
    destination: str = Field(min_length=1, max_length=100)
    start_at: datetime | None = None
    end_at: datetime | None = None
    budget: Decimal | None = Field(default=None, ge=0)
    thread_id: str | None = Field(default=None, min_length=1, max_length=100)


class TripUpdateRequest(BaseModel):
    origin: str | None = Field(default=None, min_length=1, max_length=100)
    destination: str | None = Field(default=None, min_length=1, max_length=100)
    start_at: datetime | None = None
    end_at: datetime | None = None
    budget: Decimal | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern=r"^(draft|active|completed|archived)$")


class TripResponse(BaseModel):
    """Public representation of a stored trip."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    origin: str
    destination: str
    start_at: datetime | None
    end_at: datetime | None
    budget: Decimal | None
    status: str
    created_at: datetime
    updated_at: datetime


class ItineraryItemCreateRequest(BaseModel):
    """Data accepted when appending an item to a trip."""

    day_number: int = Field(ge=1)
    sort_order: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=200)
    start_at: datetime | None = None
    end_at: datetime | None = None
    estimated_cost: Decimal = Field(default=Decimal("0"), ge=0)
    source: str | None = Field(default=None, max_length=100)


class ItineraryItemUpdateRequest(BaseModel):
    day_number: int | None = Field(default=None, ge=1)
    sort_order: int | None = Field(default=None, ge=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    start_at: datetime | None = None
    end_at: datetime | None = None
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    source: str | None = Field(default=None, max_length=100)


class ItineraryItemResponse(BaseModel):
    """Public representation of one stored itinerary item."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    day_number: int
    sort_order: int
    title: str
    location: str
    start_at: datetime | None
    end_at: datetime | None
    estimated_cost: Decimal
    source: str | None
    created_at: datetime
