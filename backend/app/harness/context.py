"""Small deterministic context compaction helpers."""

from typing import Any


def compact_messages(messages: list[Any], max_messages: int = 20) -> list[Any]:
    """Keep the first system message and the most recent conversation turns."""
    if max_messages < 2:
        raise ValueError("max_messages 必须至少为 2")
    if len(messages) <= max_messages:
        return messages.copy()
    first = messages[0]
    role = first.get("role") if isinstance(first, dict) else getattr(first, "type", None)
    if role in {"system", "SystemMessage"}:
        return [first, *messages[-(max_messages - 1) :]]
    return messages[-max_messages:]
