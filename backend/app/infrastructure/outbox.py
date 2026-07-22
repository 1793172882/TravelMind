"""MySQL outbox for retrying approved MCP writes without duplicating them."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.models.outbox_event import OutboxEventRecord


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class OutboxStore:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def enqueue(
        self,
        topic: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> OutboxEventRecord:
        with self.session_factory() as session:
            existing = session.scalar(
                select(OutboxEventRecord).where(
                    OutboxEventRecord.idempotency_key == idempotency_key
                )
            )
            if existing:
                session.expunge(existing)
                return existing
            event = OutboxEventRecord(
                topic=topic,
                payload=payload,
                idempotency_key=idempotency_key,
                available_at=_now(),
            )
            session.add(event)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = session.scalar(
                    select(OutboxEventRecord).where(
                        OutboxEventRecord.idempotency_key == idempotency_key
                    )
                )
                if existing is None:
                    raise
                session.expunge(existing)
                return existing
            session.refresh(event)
            session.expunge(event)
            return event

    def pending(self, limit: int = 20) -> list[OutboxEventRecord]:
        with self.session_factory() as session:
            statement = (
                select(OutboxEventRecord)
                .where(
                    OutboxEventRecord.status == "pending",
                    OutboxEventRecord.available_at <= _now(),
                    OutboxEventRecord.attempts < 5,
                )
                .order_by(OutboxEventRecord.id)
                .limit(limit)
            )
            rows = list(session.scalars(statement))
            for row in rows:
                session.expunge(row)
            return rows

    def get(self, event_id: int) -> OutboxEventRecord | None:
        with self.session_factory() as session:
            event = session.get(OutboxEventRecord, event_id)
            if event:
                session.expunge(event)
            return event

    def succeed(self, event_id: int) -> None:
        with self.session_factory() as session:
            event = session.get(OutboxEventRecord, event_id)
            if event:
                event.status = "completed"
                event.last_error = None
                session.commit()

    def fail(self, event_id: int, error: Exception) -> None:
        with self.session_factory() as session:
            event = session.get(OutboxEventRecord, event_id)
            if event is None:
                return
            event.attempts += 1
            event.last_error = f"{type(error).__name__}: {error}"[:2000]
            if event.attempts >= 5:
                event.status = "failed"
            else:
                event.available_at = _now() + timedelta(seconds=2**event.attempts)
            session.commit()


class OutboxWorker:
    def __init__(self, store: OutboxStore, mcp_manager: Any) -> None:
        self.store = store
        self.mcp_manager = mcp_manager
        # ponytail: one process lock is sufficient while horizontal deployment is excluded.
        self._lock = asyncio.Lock()

    async def dispatch(self, event_id: int) -> bool:
        async with self._lock:
            return await self._dispatch(event_id)

    async def _dispatch(self, event_id: int) -> bool:
        event = self.store.get(event_id)
        if event is None or event.status != "pending":
            return bool(event and event.status == "completed")
        try:
            if event.topic != "mcp.call_tool":
                raise ValueError(f"未知 Outbox topic：{event.topic}")
            await self.mcp_manager.call_tool(
                event.payload["tool"], event.payload["arguments"]
            )
        except Exception as error:
            self.store.fail(event.id, error)
            return False
        self.store.succeed(event.id)
        return True

    async def run_once(self) -> int:
        completed = 0
        for event in self.store.pending():
            completed += int(await self.dispatch(event.id))
        return completed

    async def run_forever(self, interval_seconds: float = 5) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            await self.run_once()
