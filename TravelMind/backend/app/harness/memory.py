"""Structured user preference memory with optional MySQL persistence."""

from collections.abc import Callable

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.infrastructure.models.user_preference import UserPreferenceRecord


class UserPreference(BaseModel):
    """Travel preferences worth carrying across conversation turns."""

    max_walking_distance_m: int | None = Field(default=None, ge=0)
    preferred_transport: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
    travels_with_elderly: bool | None = None


class MemoryStore:
    """Merge structured preferences by user ID."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory
        self._preferences: dict[str, UserPreference] = {}

    def get(self, user_id: str) -> UserPreference:
        """Return saved preferences or an empty preference model."""
        if self.session_factory:
            with self.session_factory() as session:
                record = session.get(UserPreferenceRecord, user_id)
                return self._from_record(record)
        return self._preferences.get(user_id, UserPreference()).model_copy(deep=True)

    def merge(self, user_id: str, update: UserPreference) -> UserPreference:
        """Overwrite explicitly supplied scalar values and merge unique lists."""
        current = self.get(user_id)
        values = current.model_dump()
        supplied = update.model_fields_set
        for field_name in supplied:
            value = getattr(update, field_name)
            if isinstance(value, list):
                values[field_name] = list(dict.fromkeys([*values[field_name], *value]))
            else:
                values[field_name] = value
        merged = UserPreference.model_validate(values)
        if self.session_factory:
            with self.session_factory() as session:
                record = session.get(UserPreferenceRecord, user_id)
                if record is None:
                    record = UserPreferenceRecord(user_id=user_id)
                    session.add(record)
                for field_name, value in merged.model_dump().items():
                    setattr(record, field_name, value)
                session.commit()
            return merged
        self._preferences[user_id] = merged
        return merged.model_copy(deep=True)

    @staticmethod
    def _from_record(record: UserPreferenceRecord | None) -> UserPreference:
        if record is None:
            return UserPreference()
        return UserPreference(
            max_walking_distance_m=record.max_walking_distance_m,
            preferred_transport=record.preferred_transport or [],
            dietary_restrictions=record.dietary_restrictions or [],
            travels_with_elderly=record.travels_with_elderly,
        )


class SavePreferenceArgs(BaseModel):
    """Only explicitly supplied preference fields are merged."""

    preference: UserPreference
