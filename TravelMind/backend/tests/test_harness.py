"""Tests for deterministic domain and Harness behavior."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import BaseModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.domain.constraints import validate_itinerary
from app.domain.models import Itinerary, ItineraryItem, TripRequirement
from app.harness.permissions import PermissionDecision, PermissionEngine, RiskLevel
from app.harness.middleware import ToolExecutor
from app.harness.recovery import retry_async
from app.harness.tool_registry import ToolDefinition, ToolRegistry
from app.infrastructure.checkpoint import TravelMindMySQLSaver
from app.tools.budget import calculate_trip_cost


def test_budget_and_constraint_validation() -> None:
    start = datetime(2026, 8, 1, 9)
    requirement = TripRequirement(
        destination="杭州",
        start_at=start,
        end_at=start + timedelta(hours=10),
        budget=Decimal("100"),
        max_walking_distance_m=1000,
        must_visit=["西湖"],
    )
    itinerary = Itinerary(
        items=[
            ItineraryItem(
                title="游览西湖",
                location="西湖",
                start_at=start,
                end_at=start + timedelta(hours=2),
                estimated_cost=Decimal("120"),
                walking_distance_m=1500,
            )
        ]
    )

    errors = validate_itinerary(requirement, itinerary)

    assert len(errors) == 2
    assert calculate_trip_cost(
        Decimal("20"), Decimal("30"), Decimal("10"), Decimal("40"), Decimal("100")
    )["remaining"] == "0"


def test_checkpoint_migrations_support_mysql_8012() -> None:
    checkpoints_table = TravelMindMySQLSaver.MIGRATIONS[1]

    assert "metadata JSON NOT NULL," in checkpoints_table
    assert "DEFAULT ('{}')" not in checkpoints_table


class EchoArgs(BaseModel):
    text: str


@pytest.mark.anyio
async def test_tool_registry_and_permission_pipeline() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="demo.echo",
            description="Return input text",
            args_model=EchoArgs,
            handler=lambda text: text,
        )
    )

    assert await registry.invoke("demo.echo", {"text": "ok"}) == "ok"
    assert PermissionEngine().decide(RiskLevel.READ) is PermissionDecision.ALLOW
    assert PermissionEngine().decide(RiskLevel.WRITE) is PermissionDecision.ASK


@pytest.mark.anyio
async def test_retry_async_stops_after_success() -> None:
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError
        return "ok"

    assert await retry_async(flaky) == "ok"
    assert calls == 2


@pytest.mark.anyio
async def test_write_tool_interrupts_and_resumes() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="demo.write",
            description="Write one value",
            args_model=EchoArgs,
            handler=lambda text: f"written:{text}",
            risk_level=RiskLevel.WRITE,
        )
    )
    executor = ToolExecutor(registry)

    async def write_node(state: dict[str, str]) -> dict[str, str]:
        result = await executor.invoke("demo.write", {"text": state["text"]})
        return {"result": result}

    graph = (
        StateGraph(dict)
        .add_node("write", write_node)
        .add_edge(START, "write")
        .add_edge("write", END)
        .compile(checkpointer=InMemorySaver())
    )
    config = {"configurable": {"thread_id": "approval-test"}}

    await graph.ainvoke({"text": "hello"}, config)
    assert (await graph.aget_state(config)).interrupts

    result = await graph.ainvoke(Command(resume=True), config)
    assert result["result"] == "written:hello"
