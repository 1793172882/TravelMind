"""Inbound webhook controllers for external messaging channels."""

import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.agent.state import AgentContext
from app.api.dependencies import resolve_agent_runtime
from app.channels.feishu import (
    EventDeduplicator,
    FEISHU_SEND_MESSAGE_TOOL,
    FeishuChannel,
    InvalidFeishuCallback,
    feishu_text_arguments,
)
from app.config import settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


async def _run_feishu_agent(
    request: Request,
    text: str,
    user_id: str,
    thread_id: str,
    chat_id: str,
    message_id: str,
) -> None:
    """Execute the slower Agent turn after the callback has been acknowledged."""
    runtime = resolve_agent_runtime(request)
    context = AgentContext(user_id=user_id, thread_id=thread_id, channel="feishu")
    pending = await runtime.pending_approvals(thread_id)
    decision = text.strip().lower()
    if pending and decision in {"批准", "同意", "approve"}:
        result = await runtime.resume(thread_id, True, context)
    elif pending and decision in {"拒绝", "不同意", "reject"}:
        result = await runtime.resume(thread_id, False, context)
    elif pending:
        result_message = "当前有待审批操作，请回复“批准”或“拒绝”。"
        await _send_feishu_reply(request, chat_id, message_id, result_message)
        return
    else:
        result = await runtime.chat(text, context)
    await _send_feishu_reply(request, chat_id, message_id, result.message)


async def _send_feishu_reply(
    request: Request,
    chat_id: str,
    message_id: str,
    text: str,
) -> None:
    """Reply to the user-initiated chat without exposing an Agent write tool."""
    manager = request.app.state.mcp_manager
    if FEISHU_SEND_MESSAGE_TOOL not in manager.tools:
        logger.warning("飞书消息工具未连接，无法回复 chat_id=%s", chat_id)
        return
    try:
        arguments = feishu_text_arguments(chat_id, text, message_id)
        outbox = getattr(request.app.state, "outbox", None)
        worker = getattr(request.app.state, "outbox_worker", None)
        if outbox and worker:
            event = outbox.enqueue(
                "mcp.call_tool",
                {"tool": FEISHU_SEND_MESSAGE_TOOL, "arguments": arguments},
                f"feishu-reply:{message_id}",
            )
            if not await worker.dispatch(event.id):
                logger.warning("飞书消息已进入 Outbox 等待重试 chat_id=%s", chat_id)
        else:
            await manager.call_tool(FEISHU_SEND_MESSAGE_TOOL, arguments)
    except Exception:
        logger.exception("飞书消息回复失败 chat_id=%s", chat_id)


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
        message.chat_id,
        message.message_id,
    )
    return {"status": "accepted", "thread_id": message.thread_id}
