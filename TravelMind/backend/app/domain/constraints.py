"""Deterministic itinerary validation independent of HTTP and LLMs."""

from app.domain.models import Itinerary, TripRequirement


def validate_itinerary(requirement: TripRequirement, itinerary: Itinerary) -> list[str]:
    """Return all hard-constraint violations in a candidate itinerary."""
    errors: list[str] = []
    if requirement.end_at <= requirement.start_at:
        errors.append("行程结束时间必须晚于开始时间")

    ordered = sorted(itinerary.items, key=lambda item: item.start_at)
    for index, item in enumerate(ordered):
        if item.end_at <= item.start_at:
            errors.append(f"{item.title} 的结束时间必须晚于开始时间")
        if item.start_at < requirement.start_at or item.end_at > requirement.end_at:
            errors.append(f"{item.title} 超出行程时间范围")
        if index and item.start_at < ordered[index - 1].end_at:
            errors.append(f"{ordered[index - 1].title} 与 {item.title} 时间重叠")

    total_cost = sum((item.estimated_cost for item in itinerary.items), start=0)
    if requirement.budget is not None and total_cost > requirement.budget:
        errors.append(f"预计费用 {total_cost} 超出预算 {requirement.budget}")

    total_walking = sum(item.walking_distance_m for item in itinerary.items)
    if (
        requirement.max_walking_distance_m is not None
        and total_walking > requirement.max_walking_distance_m
    ):
        errors.append(
            f"预计步行 {total_walking} 米超出限制 {requirement.max_walking_distance_m} 米"
        )

    searchable = " ".join(f"{item.title} {item.location}" for item in itinerary.items)
    for place in requirement.must_visit:
        if place not in searchable:
            errors.append(f"缺少必去地点：{place}")
    return errors
