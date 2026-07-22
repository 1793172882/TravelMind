"""HTTP controllers for trip operations."""

import asyncio

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.api.dependencies import CurrentUserDependency, TripServiceDependency
from app.api.schemas.trips import (
    ItineraryItemCreateRequest,
    ItineraryItemResponse,
    ItineraryItemUpdateRequest,
    TripCreateRequest,
    TripPreviewRequest,
    TripPreviewResponse,
    TripResponse,
    TripUpdateRequest,
)
from app.tools.amap import AMapAPIError, geocode, static_map_image

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post("/preview", response_model=TripPreviewResponse)
def preview_trip(request: TripPreviewRequest) -> TripPreviewResponse:
    return TripPreviewResponse(
        message=f"正在规划从{request.origin}到{request.destination}的行程"
    )


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def create_trip(
    request: TripCreateRequest,
    service: TripServiceDependency,
    user: CurrentUserDependency,
) -> TripResponse:
    """Create a trip through the application service."""
    return TripResponse.model_validate(
        service.create_trip(
            origin=request.origin,
            destination=request.destination,
            start_at=request.start_at,
            end_at=request.end_at,
            budget=request.budget,
            thread_id=user.thread_id(request.thread_id) if request.thread_id else None,
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


@router.patch("/{trip_id}", response_model=TripResponse)
def update_trip(
    trip_id: int,
    request: TripUpdateRequest,
    service: TripServiceDependency,
) -> TripResponse:
    trip = service.update_trip(trip_id, **request.model_dump(exclude_unset=True))
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripResponse.model_validate(trip)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: int, service: TripServiceDependency) -> None:
    if not service.delete_trip(trip_id):
        raise HTTPException(status_code=404, detail="Trip not found")


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


@router.patch("/{trip_id}/items/{item_id}", response_model=ItineraryItemResponse)
def update_itinerary_item(
    trip_id: int,
    item_id: int,
    request: ItineraryItemUpdateRequest,
    service: TripServiceDependency,
) -> ItineraryItemResponse:
    item = service.update_itinerary_item(
        trip_id,
        item_id,
        **request.model_dump(exclude_unset=True),
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Itinerary item not found")
    return ItineraryItemResponse.model_validate(item)


@router.delete("/{trip_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_itinerary_item(
    trip_id: int,
    item_id: int,
    service: TripServiceDependency,
) -> None:
    if not service.delete_itinerary_item(trip_id, item_id):
        raise HTTPException(status_code=404, detail="Itinerary item not found")


@router.get("/{trip_id}/map", response_class=Response)
async def trip_map(trip_id: int, service: TripServiceDependency) -> Response:
    """Proxy a static AMap image so the Web Service key stays server-side."""
    trip = service.get_trip(trip_id)
    items = service.list_itinerary_items(trip_id)
    if trip is None or items is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    names = list(dict.fromkeys([trip.origin, *(item.location for item in items), trip.destination]))
    try:
        places = await asyncio.gather(*(geocode(name) for name in names[:20]))
        image = await static_map_image([place["location"] for place in places])
    except (AMapAPIError, TimeoutError, ConnectionError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return Response(content=image, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})
