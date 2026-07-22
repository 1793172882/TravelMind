"""Small in-process event stream for Web UI progress updates."""

import asyncio
from collections import Counter, defaultdict, deque
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentEvent:
    id: int
    type: str
    data: dict[str, Any]
    created_at: str


class EventBroker:
    """Fan out transient Agent events and retain a short reconnect buffer."""

    def __init__(self, history_size: int = 100) -> None:
        # ponytail: one process is enough until the app is horizontally scaled.
        self._history_size = history_size
        self._events: dict[str, deque[AgentEvent]] = defaultdict(
            lambda: deque(maxlen=history_size)
        )
        self._subscribers: dict[str, set[asyncio.Queue[AgentEvent]]] = defaultdict(set)
        self._sequence = 0
        self._counts: Counter[str] = Counter()

    async def publish(self, thread_id: str, event_type: str, **data: Any) -> AgentEvent:
        self._sequence += 1
        event = AgentEvent(
            id=self._sequence,
            type=event_type,
            data=data,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._events[thread_id].append(event)
        self._counts[event_type] += 1
        for queue in tuple(self._subscribers[thread_id]):
            queue.put_nowait(event)
        return event

    def history(self, thread_id: str, after_id: int = 0) -> list[AgentEvent]:
        return [event for event in self._events[thread_id] if event.id > after_id]

    def metrics(self) -> dict[str, int]:
        return dict(self._counts)

    async def subscribe(self, thread_id: str, after_id: int = 0) -> AsyncIterator[AgentEvent]:
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._subscribers[thread_id].add(queue)
        try:
            for event in self.history(thread_id, after_id):
                yield event
            while True:
                yield await queue.get()
        finally:
            self._subscribers[thread_id].discard(queue)


def event_dict(event: AgentEvent) -> dict[str, Any]:
    return asdict(event)
