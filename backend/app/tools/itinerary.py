"""Deterministic itinerary validation exposed as a Harness tool."""

from typing import Any

from pydantic import BaseModel

from app.domain.constraints import validate_itinerary
from app.domain.models import Itinerary, TripRequirement


class ValidateItineraryArgs(BaseModel):
    """A candidate plan and the hard requirements it must satisfy."""

    requirement: TripRequirement
    itinerary: Itinerary


def validate_candidate_itinerary(
    requirement: TripRequirement,
    itinerary: Itinerary,
) -> dict[str, Any]:
    """Return an explicit pass/fail result for the candidate itinerary."""
    errors = validate_itinerary(requirement, itinerary)
    return {"valid": not errors, "errors": errors}
