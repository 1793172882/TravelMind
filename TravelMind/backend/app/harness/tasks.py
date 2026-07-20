"""Dependency-aware tasks for the current single Agent."""

from dataclasses import dataclass, field
from enum import StrEnum


class TaskStatus(StrEnum):
    """Lifecycle states for one Harness task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class Task:
    """One unit of durable work, represented in memory for the MVP."""

    task_id: str
    description: str
    blocked_by: set[str] = field(default_factory=set)
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    agent_id: str = "travel_agent"


class TaskStore:
    """Track tasks and expose those whose dependencies completed."""

    def __init__(self) -> None:
        # ponytail: move to MySQL when tasks must survive process restarts.
        self._tasks: dict[str, Task] = {}

    def add(self, task: Task) -> None:
        if task.task_id in self._tasks:
            raise ValueError(f"任务已存在：{task.task_id}")
        self._tasks[task.task_id] = task

    def runnable(self) -> list[Task]:
        """Return pending tasks whose dependencies are all completed."""
        completed = {
            task.task_id for task in self._tasks.values() if task.status is TaskStatus.COMPLETED
        }
        return [
            task
            for task in self._tasks.values()
            if task.status is TaskStatus.PENDING and task.blocked_by <= completed
        ]
