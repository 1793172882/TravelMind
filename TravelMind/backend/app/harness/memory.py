"""Structured user preference memory used before durable storage is added."""

from pydantic import BaseModel, Field


class UserPreference(BaseModel):
    """Travel preferences worth carrying across conversation turns."""

    max_walking_distance_m: int | None = Field(default=None, ge=0)
    preferred_transport: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
    travels_with_elderly: bool | None = None


class MemoryStore:
    """Merge structured preferences by user ID."""

    def __init__(self) -> None:
        # ponytail: in-memory until cross-process persistence is required.
        self._preferences: dict[str, UserPreference] = {}

    def get(self, user_id: str) -> UserPreference:
        """Return saved preferences or an empty preference model."""
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
        self._preferences[user_id] = merged
        return merged.model_copy(deep=True)
