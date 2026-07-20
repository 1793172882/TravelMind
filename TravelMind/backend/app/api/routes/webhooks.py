"""Inbound webhook controllers for external messaging channels."""

import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.agent.state import AgentContext
from app.api.dependencies import resolve_agent_runtime
from app.channels.feishu import (
    EventDeduplicator,
    FeishuChannel,
    InvalidFeishuCallback,
)
from app.config import settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _run_feishu_agent(request: Request, text: str, user_id: str, thread_id: str) -> None:
    """Execute the slower Agent turn after the callback has been acknowledged."""
    runtime = resolve_agent_runtime(request)
    await runtime.chat(
        text,
        AgentContext(user_id=user_id, thread_id=thread_id, channel="feishu"),
    )


@router.post("/feishu", status_code=status.HTTP_200_OK)
async def receive_feishu_event(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Verify, deduplicate, and enqueue one supported Feishu event."""
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Invalid JSON") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    if settings.feishu_verification_token is None and settings.feishu_encrypt_key is None:
        raise HTTPException(status_code=503, detail="飞书 Webhook 尚未配置")

    channel = FeishuChannel(
        verification_token=(
            settings.feishu_verification_token.get_secret_value()
            if settings.feishu_verification_token
            else None
        ),
        encrypt_key=(
            settings.feishu_encrypt_key.get_secret_value()
            if settings.feishu_encrypt_key
            else None
        ),
    )
    try:
        channel.verify(raw_body, request.headers, payload)
        challenge = channel.challenge(payload)
        if challenge is not None:
            return {"challenge": challenge}
        message = channel.parse_text_message(payload)
    except InvalidFeishuCallback as error:
        raise HTTPException(status_code=401, detail=str(error)) from error

    if message is None:
        return {"status": "ignored"}
    deduplicator: EventDeduplicator = request.app.state.feishu_events
    if not deduplicator.first_seen(message.event_id):
        return {"status": "duplicate", "thread_id": message.thread_id}

    background_tasks.add_task(
        _run_feishu_agent,
        request,
        message.text,
        message.user_id,
        message.thread_id,
    )
    return {"status": "accepted", "thread_id": message.thread_id}
