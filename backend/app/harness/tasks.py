"""Dependency-aware tasks for the current single Agent."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.harness.runtime_context import require_agent_context
from app.infrastructure.models.harness_task import HarnessTaskRecord


class TaskStatus(StrEnum):
    """Lifecycle states for one Harness task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class Task:
    """One unit of durable work."""

    task_id: str
    description: str
    user_id: str = "anonymous"
    thread_id: str = "default"
    blocked_by: set[str] = field(default_factory=set)
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    agent_id: str = "travel_agent"


class TaskStore:
    """Track tasks and expose those whose dependencies completed."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory
        self._tasks: dict[str, Task] = {}

    def add(self, task: Task) -> None:
        if self.session_factory:
            with self.session_factory() as session:
                if session.get(HarnessTaskRecord, task.task_id):
                    raise ValueError(f"任务已存在：{task.task_id}")
                session.add(self._record(task))
                session.commit()
            return
        if task.task_id in self._tasks:
            raise ValueError(f"任务已存在：{task.task_id}")
        self._tasks[task.task_id] = task

    def runnable(self, *, user_id: str | None = None, thread_id: str | None = None) -> list[Task]:
        """Return pending tasks whose dependencies are all completed."""
        tasks = self.list(user_id=user_id, thread_id=thread_id)
        completed = {
            task.task_id for task in tasks if task.status is TaskStatus.COMPLETED
        }
        return [
            task
            for task in tasks
            if task.status is TaskStatus.PENDING and task.blocked_by <= completed
        ]

    def list(self, *, user_id: str | None = None, thread_id: str | None = None) -> list[Task]:
        if not self.session_factory:
            return [
                task
                for task in self._tasks.values()
                if (user_id is None or task.user_id == user_id)
                and (thread_id is None or task.thread_id == thread_id)
            ]
        with self.session_factory() as session:
            statement = select(HarnessTaskRecord).order_by(HarnessTaskRecord.created_at)
            if user_id is not None:
                statement = statement.where(HarnessTaskRecord.user_id == user_id)
            if thread_id is not None:
                statement = statement.where(HarnessTaskRecord.thread_id == thread_id)
            return [self._task(row) for row in session.scalars(statement)]

    def complete(self, task_id: str, result: str | None = None) -> Task:
        if not self.session_factory:
            task = self._tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.result = result
            return task
        with self.session_factory() as session:
            record = session.get(HarnessTaskRecord, task_id)
            if record is None:
                raise KeyError(f"未知任务：{task_id}")
            record.status = TaskStatus.COMPLETED.value
            record.result = result
            session.commit()
            session.refresh(record)
            return self._task(record)

    @staticmethod
    def _record(task: Task) -> HarnessTaskRecord:
        return HarnessTaskRecord(
            task_id=task.task_id,
            description=task.description,
            user_id=task.user_id,
            thread_id=task.thread_id,
            blocked_by=sorted(task.blocked_by),
            status=task.status.value,
            result=task.result,
            agent_id=task.agent_id,
        )

    @staticmethod
    def _task(record: HarnessTaskRecord) -> Task:
        return Task(
            task_id=record.task_id,
            description=record.description,
            user_id=record.user_id,
            thread_id=record.thread_id,
            blocked_by=set(record.blocked_by or []),
            status=TaskStatus(record.status),
            result=record.result,
            agent_id=record.agent_id,
        )


class CreateTaskArgs(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    blocked_by: list[str] = Field(default_factory=list)


class CompleteTaskArgs(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    result: str | None = Field(default=None, max_length=10_000)


class ListTasksArgs(BaseModel):
    runnable_only: bool = False


def new_task(description: str, blocked_by: list[str]) -> Task:
    context = require_agent_context()
    return Task(
        task_id=uuid4().hex,
        description=description,
        user_id=context.user_id,
        thread_id=context.thread_id,
        blocked_by=set(blocked_by),
        agent_id=context.agent_id,
    )
