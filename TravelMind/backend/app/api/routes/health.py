from fastapi import APIRouter

router = APIRouter(tags=["operations"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "TravelMind"}

@router.get("/version")
def version() -> dict[str, str]:
    return {"name": "TravelMind","version": "0.1.0"}
