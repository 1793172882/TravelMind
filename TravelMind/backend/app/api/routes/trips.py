"""Trip query, replan, and archive endpoints; implemented in stages 3 and 8."""
from typing import Dict

from app.api.schemas.trips import TripPreviewRequest, TripPreviewResponse
from fastapi import APIRouter

router = APIRouter(prefix="/trips", tags=["trips"])

@router.post("/preview",response_model= TripPreviewResponse)
def preview_trip(request: TripPreviewRequest) -> TripPreviewResponse:
   return TripPreviewResponse(
     message=f"正在规划从{request.origin}到{request.destination}的行程"
  )

@router.get("/{trip_id}")
def get_trip(trip_id: int, detail: bool = False,language: str = "zh") -> dict:
   return {
      "trip_id" : trip_id,
      "detail" : detail,
      "language" : language
   }
