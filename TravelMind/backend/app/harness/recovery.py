"""Classify failures and apply bounded retries."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

ResultT = TypeVar("ResultT")


async def retry_async(
    operation: Callable[[], Awaitable[ResultT]],
    *,
    attempts: int = 2,
    delay_seconds: float = 0,
    retry_on: tuple[type[Exception], ...] = (TimeoutError, ConnectionError),
) -> ResultT:
    """Retry transient failures with an explicit upper bound."""
    if attempts < 1:
        raise ValueError("attempts 必须至少为 1")
    for attempt in range(attempts):
        try:
            return await operation()
        except retry_on:
            if attempt == attempts - 1:
                raise
            if delay_seconds:
                await asyncio.sleep(delay_seconds)
    raise RuntimeError("unreachable")
