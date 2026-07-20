"""Build and invoke the LangChain v1 single Agent."""

from dataclasses import dataclass, field
from typing import Any, Literal

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import AgentContext
from app.config import settings
from app.harness.middleware import ToolExecutor
from app.harness.permissions import RiskLevel
from app.harness.tool_registry import ToolDefinition, ToolRegistry
from app.tools.budget import BudgetArgs, calculate_trip_cost
from app.tools.itinerary import ValidateItineraryArgs, validate_candidate_itinerary
from app.tools.amap import (
    GeocodeArgs,
    RouteArgs,
    SearchPOIArgs,
    geocode,
    plan_route,
    search_poi,
)
from app.tools.trips import (
    AddItineraryItemArgs,
    CreateTripArgs,
    TripIdArgs,
    add_itinerary_item_record,
    create_trip_record,
    get_trip_record,
)
from app.tools.weather import WeatherArgs, query_weather


def build_default_registry() -> ToolRegistry:
    """Register the local tools available in the first runnable Agent."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="budget.calculate_trip_cost",
            description="计算交通、住宿、餐饮和活动总费用，并判断是否超出预算。",
            args_model=BudgetArgs,
            handler=calculate_trip_cost,
            risk_level=RiskLevel.READ,
        )
    )
    registry.register(
        ToolDefinition(
            name="itinerary.validate",
            description="保存前校验候选行程的时间重叠、预算、步行距离和必去地点。",
            args_model=ValidateItineraryArgs,
            handler=validate_candidate_itinerary,
            risk_level=RiskLevel.READ,
        )
    )
    if settings.amap_api_key is not None:
        registry.register(
            ToolDefinition(
                name="amap.geocode",
                description="使用高德地图把中国地址或地点名称转换为经纬度和行政区编码。",
                args_model=GeocodeArgs,
                handler=geocode,
                risk_level=RiskLevel.READ,
            )
        )
        registry.register(
            ToolDefinition(
                name="amap.search_poi",
                description="使用高德地图在指定城市搜索真实景点、餐厅、酒店等地点。",
                args_model=SearchPOIArgs,
                handler=search_poi,
                risk_level=RiskLevel.READ,
            )
        )
        registry.register(
            ToolDefinition(
                name="amap.weather",
                description="使用高德地图按城市名称或 adcode 查询当前天气或未来天气。",
                args_model=WeatherArgs,
                handler=query_weather,
                risk_level=RiskLevel.READ,
            )
        )
        registry.register(
            ToolDefinition(
                name="amap.plan_route",
                description="使用高德地图规划步行、驾车或公交路线，地点可直接传中文名称。",
                args_model=RouteArgs,
                handler=plan_route,
                risk_level=RiskLevel.READ,
            )
        )
    registry.register(
        ToolDefinition(
            name="trip.create",
            description="在 MySQL 中创建行程草稿。只有用户明确要保存方案时才调用。",
            args_model=CreateTripArgs,
            handler=create_trip_record,
            risk_level=RiskLevel.WRITE,
        )
    )
    registry.register(
        ToolDefinition(
            name="trip.get",
            description="按行程 ID 查询已保存的行程和全部日程项。",
            args_model=TripIdArgs,
            handler=get_trip_record,
            risk_level=RiskLevel.READ,
        )
    )
    registry.register(
        ToolDefinition(
            name="trip.add_itinerary_item",
            description="向已存在的行程草稿追加一个有时间、地点和费用的日程项。",
            args_model=AddItineraryItemArgs,
            handler=add_itinerary_item_record,
            risk_level=RiskLevel.WRITE,
        )
    )
    return registry


def _langchain_tools(executor: ToolExecutor) -> list[BaseTool]:
    """Adapt Harness tools to LangChain while retaining the execution pipeline."""
    tools: list[BaseTool] = []
    for definition in executor.registry.list_tools():

        async def invoke_tool(
            _tool_name: str = definition.name,
            **arguments: Any,
        ) -> Any:
            return await executor.invoke(_tool_name, arguments)

        tools.append(
            StructuredTool.from_function(
                coroutine=invoke_tool,
                name=definition.name.replace(".", "__"),
                description=definition.description,
                args_schema=definition.args_model,
            )
        )
    return tools


class TravelAgentRuntime:
    """Expose a stable chat method over the compiled LangChain/LangGraph agent."""

    def __init__(self, agent: Any) -> None:
        self.agent = agent

    async def chat(self, message: str, context: AgentContext) -> "AgentRunResult":
        """Continue one checkpointed conversation and report completion or approval."""
        config = {"configurable": {"thread_id": context.thread_id}}
        result = await self.agent.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            context=context,
        )
        return await self._result(result, config)

    async def pending_approvals(self, thread_id: str) -> list[Any]:
        """Return current LangGraph interrupt payloads for a thread."""
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = await self.agent.aget_state(config)
        return [item.value for item in snapshot.interrupts]

    async def resume(
        self,
        thread_id: str,
        approved: bool,
        context: AgentContext,
    ) -> "AgentRunResult":
        """Resume a thread paused by a Harness approval interrupt."""
        config = {"configurable": {"thread_id": thread_id}}
        result = await self.agent.ainvoke(
            Command(resume=approved),
            config=config,
            context=context,
        )
        return await self._result(result, config)

    async def _result(self, result: dict[str, Any], config: dict[str, Any]) -> "AgentRunResult":
        snapshot = await self.agent.aget_state(config)
        pending = [item.value for item in snapshot.interrupts]
        if pending:
            return AgentRunResult(
                status="waiting_approval",
                message="该操作需要你的审批。",
                pending_approvals=pending,
            )
        content = result["messages"][-1].content
        if isinstance(content, str):
            text = content
        else:
            text = "".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        return AgentRunResult(status="completed", message=text)


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    """Stable result returned by chat and approval APIs."""

    status: Literal["completed", "waiting_approval"]
    message: str
    pending_approvals: list[Any] = field(default_factory=list)


def build_agent_runtime(
    *,
    model: BaseChatModel | None = None,
    registry: ToolRegistry | None = None,
) -> TravelAgentRuntime:
    """Build the real model runtime or accept a Fake model for tests."""
    if model is None:
        api_key = settings.model_api_key or settings.dashscope_api_key
        if api_key is None:
            raise RuntimeError("缺少 DASHSCOPE_API_KEY，无法启动千问 Agent")
        model = ChatOpenAI(
            model=settings.model_name,
            api_key=api_key,
            base_url=settings.model_base_url,
            temperature=0,
        )
    executor = ToolExecutor(registry or build_default_registry())
    agent = create_agent(
        model=model,
        tools=_langchain_tools(executor),
        system_prompt=SYSTEM_PROMPT,
        context_schema=AgentContext,
        checkpointer=InMemorySaver(),
        name="travel_agent",
    )
    return TravelAgentRuntime(agent)
