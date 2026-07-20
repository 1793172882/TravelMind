"""HTTP controllers for trip operations."""

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import TripServiceDependency
from app.api.schemas.trips import (
    ItineraryItemCreateRequest,
    ItineraryItemResponse,
    TripCreateRequest,
    TripPreviewRequest,
    TripPreviewResponse,
    TripResponse,
)

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post("/preview", response_model=TripPreviewResponse)
def preview_trip(request: TripPreviewRequest) -> TripPreviewResponse:
    return TripPreviewResponse(
        message=f"正在规划从{request.origin}到{request.destination}的行程"
    )


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def create_trip(request: TripCreateRequest, service: TripServiceDependency) -> TripResponse:
    """Create a trip through the application service."""
    return TripResponse.model_validate(
        service.create_trip(
            origin=request.origin,
            destination=request.destination,
            start_at=request.start_at,
            end_at=request.end_at,
            budget=request.budget,
        )
    )


@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(trip_id: int, service: TripServiceDependency) -> TripResponse:
    """Query one trip through the application service."""
    trip = service.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripResponse.model_validate(trip)


@router.get("", response_model=list[TripResponse])
def list_trips(service: TripServiceDependency) -> list[TripResponse]:
    """Return all stored trips."""
    return [TripResponse.model_validate(trip) for trip in service.list_trips()]


@router.post("/{trip_id}/archive", response_model=TripResponse)
def archive_trip(trip_id: int, service: TripServiceDependency) -> TripResponse:
    """Archive one stored trip."""
    trip = service.archive_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripResponse.model_validate(trip)


@router.post(
    "/{trip_id}/items",
    response_model=ItineraryItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_itinerary_item(
    trip_id: int,
    request: ItineraryItemCreateRequest,
    service: TripServiceDependency,
) -> ItineraryItemResponse:
    """Append one itinerary item to an existing trip."""
    item = service.add_itinerary_item(trip_id=trip_id, **request.model_dump())
    if item is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return ItineraryItemResponse.model_validate(item)


@router.get("/{trip_id}/items", response_model=list[ItineraryItemResponse])
def list_itinerary_items(
    trip_id: int,
    service: TripServiceDependency,
) -> list[ItineraryItemResponse]:
    """Return all itinerary items for a trip."""
    items = service.list_itinerary_items(trip_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return [ItineraryItemResponse.model_validate(item) for item in items]
