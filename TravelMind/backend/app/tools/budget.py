"""Deterministic Decimal-based trip cost calculation."""

from decimal import Decimal

from pydantic import BaseModel, Field


class BudgetArgs(BaseModel):
    """Validated arguments exposed to the Agent budget tool."""

    transport: Decimal = Field(ge=0)
    accommodation: Decimal = Field(ge=0)
    food: Decimal = Field(ge=0)
    activities: Decimal = Field(ge=0)
    budget: Decimal = Field(ge=0)


def calculate_trip_cost(
    transport: Decimal,
    accommodation: Decimal,
    food: Decimal,
    activities: Decimal,
    budget: Decimal,
) -> dict[str, str | bool]:
    """Calculate total cost, remaining budget, and overspend status."""
    values = (transport, accommodation, food, activities, budget)
    if any(value < 0 for value in values):
        raise ValueError("金额不能为负数")
    total = sum(values[:4], start=Decimal("0"))
    remaining = budget - total
    return {
        "total": str(total),
        "budget": str(budget),
        "remaining": str(remaining),
        "over_budget": remaining < 0,
    }
