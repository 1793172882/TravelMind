"""Tests for the inbound Feishu channel boundary."""

import hashlib
import json

import pytest

from app.channels.feishu import EventDeduplicator, FeishuChannel, InvalidFeishuCallback


def _event() -> dict[str, object]:
    return {
        "header": {
            "event_id": "event-1",
            "event_type": "im.message.receive_v1",
            "token": "verify-me",
        },
        "event": {
            "sender": {"sender_id": {"open_id": "ou-user"}},
            "message": {
                "message_id": "message-1",
                "chat_id": "chat-1",
                "message_type": "text",
                "content": json.dumps({"text": "规划杭州一日游"}),
            },
        },
    }


def test_feishu_signature_token_and_message_mapping() -> None:
    payload = _event()
    raw_body = json.dumps(payload).encode()
    signature = hashlib.sha256(b"1" + b"n" + b"encrypt-me" + raw_body).hexdigest()
    channel = FeishuChannel(
        verification_token="verify-me",
        encrypt_key="encrypt-me",
    )

    channel.verify(
        raw_body,
        {
            "x-lark-request-timestamp": "1",
            "x-lark-request-nonce": "n",
            "x-lark-signature": signature,
        },
        payload,
    )
    message = channel.parse_text_message(payload)

    assert message is not None
    assert message.user_id == "feishu:ou-user"
    assert message.thread_id == "feishu:chat-1"
    assert message.text == "规划杭州一日游"


def test_feishu_rejects_wrong_token_and_deduplicates() -> None:
    payload = _event()
    channel = FeishuChannel(verification_token="wrong")

    with pytest.raises(InvalidFeishuCallback):
        channel.verify(json.dumps(payload).encode(), {}, payload)

    events = EventDeduplicator()
    assert events.first_seen("event-1") is True
    assert events.first_seen("event-1") is False
