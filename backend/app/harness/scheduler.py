"""Minimal MySQL scheduler for 24-hour and 2-hour pre-trip weather replanning."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.infrastructure.models.scheduled_job import ScheduledJobRecord
from app.infrastructure.models.trip import Trip
from app.tools.weather import query_weather

Replanner = Callable[[ScheduledJobRecord, Trip, dict], Awaitable[str]]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def schedule_trip_weather_checks(session: Session, trip: Trip) -> None:
    if trip.start_at is None:
        cancel_trip_weather_checks(session, trip.id)
        return
    for kind, before in (("weather_24h", timedelta(hours=24)), ("weather_2h", timedelta(hours=2))):
        run_at = trip.start_at - before
        existing = session.scalar(
            select(ScheduledJobRecord).where(
                ScheduledJobRecord.trip_id == trip.id,
                ScheduledJobRecord.kind == kind,
            )
        )
        if run_at > _now():
            if existing is None:
                session.add(ScheduledJobRecord(
                    trip_id=trip.id,
                    user_id=trip.owner_id,
                    thread_id=trip.thread_id,
                    kind=kind,
                    run_at=run_at,
                ))
            else:
                existing.run_at = run_at
                existing.status = "pending"
                existing.attempts = 0
                existing.result = None
                existing.last_error = None
        elif existing and existing.status == "pending":
            existing.status = "cancelled"


def cancel_trip_weather_checks(session: Session, trip_id: int) -> None:
    session.execute(
        update(ScheduledJobRecord)
        .where(
            ScheduledJobRecord.trip_id == trip_id,
            ScheduledJobRecord.status == "pending",
        )
        .values(status="cancelled")
    )


class Scheduler:
    def __init__(self, session_factory: Callable[[], Session], replanner: Replanner) -> None:
        self.session_factory = session_factory
        self.replanner = replanner
        self._lock = asyncio.Lock()

    def list_jobs(self, user_id: str) -> list[ScheduledJobRecord]:
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(ScheduledJobRecord)
                    .where(ScheduledJobRecord.user_id == user_id)
                    .order_by(ScheduledJobRecord.run_at)
                )
            )
            for row in rows:
                session.expunge(row)
            return rows

    def _due(self) -> list[int]:
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(ScheduledJobRecord)
                    .where(
                        ScheduledJobRecord.status == "pending",
                        ScheduledJobRecord.run_at <= _now(),
                        ScheduledJobRecord.attempts < 3,
                    )
                    .order_by(ScheduledJobRecord.run_at)
                    .limit(10)
                )
            )
            return [row.id for row in rows]

    async def run_once(self) -> int:
        async with self._lock:
            completed = 0
            for job_id in self._due():
                completed += int(await self._run_job(job_id))
            return completed

    async def _run_job(self, job_id: int) -> bool:
        with self.session_factory() as session:
            job = session.get(ScheduledJobRecord, job_id)
            if job is None or job.status != "pending":
                return False
            trip = session.get(Trip, job.trip_id)
            if trip is None:
                job.status = "cancelled"
                session.commit()
                return False
            session.expunge(job)
            session.expunge(trip)
        try:
            weather = await query_weather(trip.destination)
            advice = await self.replanner(job, trip, weather)
        except Exception as error:
            with self.session_factory() as session:
                stored = session.get(ScheduledJobRecord, job_id)
                if stored:
                    stored.attempts += 1
                    stored.last_error = f"{type(error).__name__}: {error}"[:2000]
                    if stored.attempts >= 3:
                        stored.status = "failed"
                    session.commit()
            return False
        with self.session_factory() as session:
            stored = session.get(ScheduledJobRecord, job_id)
            if stored:
                stored.status = "completed"
                stored.result = {"weather": weather, "advice": advice}
                stored.last_error = None
                session.commit()
        return True

    async def run_forever(self, interval_seconds: float = 60) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            await self.run_once()
