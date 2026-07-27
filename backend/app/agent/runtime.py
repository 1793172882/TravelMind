"""Build and invoke the LangChain v1 single Agent."""

from dataclasses import dataclass, field
from typing import Any, Literal

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, SummarizationMiddleware, dynamic_prompt
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import AgentContext
from app.config import settings
from app.harness.middleware import ToolExecutor
from app.harness.events import EventBroker
from app.harness.memory import MemoryStore, SavePreferenceArgs
from app.harness.permissions import RiskLevel
from app.harness.runtime_context import current_agent_context, require_agent_context
from app.harness.skills import LoadSkillArgs, SkillLoader
from app.harness.tasks import (
    CompleteTaskArgs,
    CreateTaskArgs,
    ListTasksArgs,
    TaskStore,
    new_task,
)
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
    SaveItineraryArgs,
    TripIdArgs,
    add_itinerary_item_record,
    create_trip_record,
    get_trip_record,
    save_itinerary_record,
)
from app.tools.weather import WeatherArgs, query_weather
from app.rag.vector_store import ChromaKnowledgeStore
from app.tools.knowledge import KnowledgeSearchArgs, search_knowledge


def build_default_registry(
    *,
    memory_store: MemoryStore | None = None,
    task_store: TaskStore | None = None,
    skill_loader: SkillLoader | None = None,
    knowledge_store: ChromaKnowledgeStore | None = None,
) -> ToolRegistry:
    """Register the local tools available in the first runnable Agent."""
    memory_store = memory_store or MemoryStore()
    task_store = task_store or TaskStore()
    registry = ToolRegistry()
    if knowledge_store is not None:
        registry.register(
            ToolDefinition(
                name="knowledge.search",
                description=(
                    "检索当前用户上传的攻略、政策和旅行资料。仅用于非实时知识，"
                    "回答必须标明返回结果中的来源；天气和路线仍使用高德工具。"
                ),
                args_model=KnowledgeSearchArgs,
                handler=lambda query, city, category, top_k: search_knowledge(
                    knowledge_store,
                    query=query,
                    city=city,
                    category=category,
                    top_k=top_k,
                ),
                risk_level=RiskLevel.READ,
            )
        )
    registry.register(
        ToolDefinition(
            name="memory.save_preferences",
            description="保存用户明确表达的长期出行偏好；不要推测或保存敏感信息。",
            args_model=SavePreferenceArgs,
            handler=lambda preference: memory_store.merge(
                require_agent_context().user_id, preference
            ).model_dump(),
            risk_level=RiskLevel.WRITE,
        )
    )
    registry.register(
        ToolDefinition(
            name="task.create",
            description="为当前复杂规划创建一个可追踪、可依赖的单 Agent 任务。",
            args_model=CreateTaskArgs,
            handler=lambda description, blocked_by: _add_task(
                task_store, description, blocked_by
            ),
            risk_level=RiskLevel.WRITE,
        )
    )
    registry.register(
        ToolDefinition(
            name="task.list",
            description="查询当前会话的全部任务或当前可执行任务。",
            args_model=ListTasksArgs,
            handler=lambda runnable_only: _list_tasks(task_store, runnable_only),
        )
    )
    registry.register(
        ToolDefinition(
            name="task.complete",
            description="完成当前会话中的一个任务并记录结果。",
            args_model=CompleteTaskArgs,
            handler=lambda task_id, result: _task_dict(task_store.complete(task_id, result)),
            risk_level=RiskLevel.WRITE,
        )
    )
    if skill_loader is not None:
        registry.register(
            ToolDefinition(
                name="skill.load",
                description="按名称加载一个出行 Skill 的完整操作说明。",
                args_model=LoadSkillArgs,
                handler=skill_loader.load_by_name,
            )
        )
    registry.register(
        ToolDefinition(
            name="trip.save_itinerary",
            description="确定性复验候选方案，并在一个MySQL事务中保存行程和全部日程项。",
            args_model=SaveItineraryArgs,
            handler=save_itinerary_record,
            risk_level=RiskLevel.WRITE,
        )
    )
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


def _add_task(store: TaskStore, description: str, blocked_by: list[str]) -> dict[str, Any]:
    task = new_task(description, blocked_by)
    store.add(task)
    return _task_dict(task)


def _list_tasks(store: TaskStore, runnable_only: bool) -> list[dict[str, Any]]:
    context = require_agent_context()
    values = (
        store.runnable(user_id=context.user_id, thread_id=context.thread_id)
        if runnable_only
        else store.list(user_id=context.user_id, thread_id=context.thread_id)
    )
    return [_task_dict(task) for task in values]


def _task_dict(task: Any) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "description": task.description,
        "blocked_by": sorted(task.blocked_by),
        "status": task.status.value,
        "result": task.result,
    }


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

    def __init__(self, agent: Any, events: EventBroker | None = None) -> None:
        self.agent = agent
        self.events = events

    async def chat(self, message: str, context: AgentContext) -> "AgentRunResult":
        """Continue one checkpointed conversation and report completion or approval."""
        config = {"configurable": {"thread_id": context.thread_id}}
        token = current_agent_context.set(context)
        try:
            if self.events:
                await self.events.publish(context.thread_id, "run.started")
            result = await self.agent.ainvoke(
                {"messages": [{"role": "user", "content": message}]},
                config=config,
                context=context,
            )
            response = await self._result(result, config)
            if self.events:
                await self.events.publish(
                    context.thread_id,
                    "run.completed" if response.status == "completed" else "run.paused",
                    status=response.status,
                )
            return response
        finally:
            current_agent_context.reset(token)

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
        token = current_agent_context.set(context)
        try:
            if self.events:
                await self.events.publish(
                    context.thread_id, "approval.decided", approved=approved
                )
            result = await self.agent.ainvoke(
                Command(resume=approved),
                config=config,
                context=context,
            )
            response = await self._result(result, config)
            if self.events:
                await self.events.publish(
                    context.thread_id,
                    "run.completed" if response.status == "completed" else "run.paused",
                    status=response.status,
                )
            return response
        finally:
            current_agent_context.reset(token)

    async def history(self, thread_id: str) -> list[dict[str, str]]:
        """Return checkpointed human/assistant messages for the Web client."""
        snapshot = await self.agent.aget_state({"configurable": {"thread_id": thread_id}})
        rows: list[dict[str, str]] = []
        for message in snapshot.values.get("messages", []):
            role = getattr(message, "type", "")
            if role not in {"human", "ai"}:
                continue
            content = getattr(message, "content", "")
            if isinstance(content, str) and content:
                rows.append({"role": "user" if role == "human" else "agent", "text": content})
        return rows

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
    checkpointer: BaseCheckpointSaver | None = None,
    memory_store: MemoryStore | None = None,
    task_store: TaskStore | None = None,
    skill_loader: SkillLoader | None = None,
    events: EventBroker | None = None,
    knowledge_store: ChromaKnowledgeStore | None = None,
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
    memory_store = memory_store or MemoryStore()
    skill_loader = skill_loader or SkillLoader(settings.skills_path)
    executor = ToolExecutor(
        registry
        or build_default_registry(
            memory_store=memory_store,
            task_store=task_store,
            skill_loader=skill_loader,
            knowledge_store=knowledge_store,
        ),
        events=events,
    )

    @dynamic_prompt
    def contextual_prompt(request: ModelRequest) -> str:
        context = request.runtime.context
        preference = memory_store.get(context.user_id).model_dump(exclude_none=True)
        return (
            f"{SYSTEM_PROMPT}\n"
            f"当前用户偏好：{preference or '暂无'}\n"
            f"可按需调用 skill.load 加载以下 Skill：\n{skill_loader.catalog()}"
        )

    agent = create_agent(
        model=model,
        tools=_langchain_tools(executor),
        middleware=[
            contextual_prompt,
            SummarizationMiddleware(
                model=model,
                trigger=("messages", settings.context_compact_trigger_messages),
                keep=("messages", settings.context_compact_keep_messages),
            ),
        ],
        context_schema=AgentContext,
        checkpointer=checkpointer or InMemorySaver(),
        name="travel_agent",
    )
    return TravelAgentRuntime(agent, events)
