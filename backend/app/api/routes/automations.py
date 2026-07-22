"""Visibility and manual execution for durable travel automations."""

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.dependencies import CurrentUserDependency

router = APIRouter(prefix="/automations", tags=["automations"])


class AutomationResponse(BaseModel):
    id: int
    trip_id: int
    kind: str
    run_at: datetime
    status: str
    attempts: int
    result: dict | None
    last_error: str | None


@router.get("", response_model=list[AutomationResponse])
def list_automations(
    request: Request,
    user: CurrentUserDependency,
) -> list[AutomationResponse]:
    return [AutomationResponse.model_validate(job) for job in request.app.state.scheduler.list_jobs(user.user_id)]


@router.post("/run")
async def run_due_automations(request: Request, user: CurrentUserDependency) -> dict[str, int]:
    del user
    return {"completed": await request.app.state.scheduler.run_once()}
