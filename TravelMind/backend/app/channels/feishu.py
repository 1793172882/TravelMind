"""Verify Feishu callbacks and map text messages to Agent context."""

import hashlib
import hmac
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any, Mapping

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.models.webhook_event import WebhookEventRecord


class InvalidFeishuCallback(ValueError):
    """Raised when a callback is unauthenticated or malformed."""


@dataclass(frozen=True, slots=True)
class FeishuTextMessage:
    """Normalized text message consumed by TravelMind."""

    event_id: str
    message_id: str
    chat_id: str
    user_id: str
    text: str

    @property
    def thread_id(self) -> str:
        """Keep one Agent conversation per Feishu chat."""
        return f"feishu:{self.chat_id}"


class EventDeduplicator:
    """Bound duplicate webhook retries in one application process."""

    def __init__(
        self,
        ttl_seconds: int = 86_400,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.session_factory = session_factory
        self._seen: dict[str, float] = {}
        self._lock = Lock()

    def first_seen(self, event_id: str) -> bool:
        """Return False when the same event was accepted within the TTL."""
        if self.session_factory:
            now = datetime.now(UTC).replace(tzinfo=None)
            with self.session_factory() as session:
                record = session.get(WebhookEventRecord, event_id)
                if record is not None and record.expires_at > now:
                    return False
                if record is not None:
                    session.delete(record)
                    session.flush()
                session.add(
                    WebhookEventRecord(
                        event_id=event_id,
                        expires_at=now + timedelta(seconds=self.ttl_seconds),
                    )
                )
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    return False
                return True
        now = time.monotonic()
        with self._lock:
            self._seen = {
                key: seen_at
                for key, seen_at in self._seen.items()
                if now - seen_at < self.ttl_seconds
            }
            if event_id in self._seen:
                return False
            self._seen[event_id] = now
            return True


class FeishuChannel:
    """Authenticate callback payloads and normalize supported events."""

    def __init__(
        self,
        *,
        verification_token: str | None = None,
        encrypt_key: str | None = None,
    ) -> None:
        self.verification_token = verification_token
        self.encrypt_key = encrypt_key

    def verify(
        self,
        raw_body: bytes,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
    ) -> None:
        """Verify the optional callback signature and verification token."""
        if self.encrypt_key:
            timestamp = headers.get("x-lark-request-timestamp", "")
            nonce = headers.get("x-lark-request-nonce", "")
            signature = headers.get("x-lark-signature", "")
            expected = hashlib.sha256(
                timestamp.encode()
                + nonce.encode()
                + self.encrypt_key.encode()
                + raw_body
            ).hexdigest()
            if not signature or not hmac.compare_digest(signature, expected):
                raise InvalidFeishuCallback("飞书回调签名无效")

        if self.verification_token:
            header = payload.get("header")
            token = header.get("token") if isinstance(header, Mapping) else payload.get("token")
            if not isinstance(token, str) or not hmac.compare_digest(
                token, self.verification_token
            ):
                raise InvalidFeishuCallback("飞书 verification token 无效")

    @staticmethod
    def challenge(payload: Mapping[str, Any]) -> str | None:
        """Return the URL-verification challenge when present."""
        challenge = payload.get("challenge")
        return challenge if isinstance(challenge, str) else None

    @staticmethod
    def parse_text_message(payload: Mapping[str, Any]) -> FeishuTextMessage | None:
        """Normalize ``im.message.receive_v1`` text events; ignore other events."""
        header = payload.get("header")
        event = payload.get("event")
        if not isinstance(header, Mapping) or not isinstance(event, Mapping):
            raise InvalidFeishuCallback("飞书事件缺少 header 或 event")
        if header.get("event_type") != "im.message.receive_v1":
            return None

        message = event.get("message")
        sender = event.get("sender")
        if not isinstance(message, Mapping) or not isinstance(sender, Mapping):
            raise InvalidFeishuCallback("飞书消息缺少 message 或 sender")
        if message.get("message_type") != "text":
            return None

        sender_id = sender.get("sender_id")
        if not isinstance(sender_id, Mapping):
            raise InvalidFeishuCallback("飞书消息缺少 sender_id")
        try:
            content = json.loads(str(message["content"]))
            text = str(content["text"]).strip()
            event_id = str(header["event_id"])
            message_id = str(message["message_id"])
            chat_id = str(message["chat_id"])
            open_id = str(sender_id["open_id"])
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise InvalidFeishuCallback("飞书文本消息字段无效") from error
        if not text:
            raise InvalidFeishuCallback("飞书文本消息不能为空")
        return FeishuTextMessage(
            event_id=event_id,
            message_id=message_id,
            chat_id=chat_id,
            user_id=f"feishu:{open_id}",
            text=text,
        )
