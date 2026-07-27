import asyncio
import json
import logging
import time
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextlib import suppress
from uuid import uuid4

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.agent.runtime import build_agent_runtime, build_default_registry
from app.agent.state import AgentContext
from app.api.router import api_router
from app.channels.feishu import EventDeduplicator
from app.channels.feishu import FEISHU_SEND_MESSAGE_TOOL, feishu_text_arguments
from app.config import PROJECT_ROOT, settings
from app.infrastructure.checkpoint import TravelMindMySQLSaver
from app.infrastructure.database import SessionLocal, ensure_application_tables
from app.infrastructure.outbox import OutboxStore, OutboxWorker
from app.harness.events import EventBroker
from app.harness.memory import MemoryStore
from app.harness.skills import SkillLoader
from app.harness.tasks import TaskStore
from app.harness.scheduler import Scheduler
from app.mcp.config import MCPConfig
from app.mcp.manager import MCPManager
from app.mcp.tool_adapter import register_mcp_tools
from app.rag.vector_store import build_knowledge_store


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start optional MCP sessions and close them with the application."""
    ensure_application_tables()
    memory_store = MemoryStore(SessionLocal)
    task_store = TaskStore(SessionLocal)
    skill_loader = SkillLoader(settings.skills_path)
    events = EventBroker()
    knowledge_store = (
        build_knowledge_store()
        if settings.dashscope_api_key is not None or settings.model_api_key is not None
        else None
    )
    registry = build_default_registry(
        memory_store=memory_store,
        task_store=task_store,
        skill_loader=skill_loader,
        knowledge_store=knowledge_store,
    )
    manager = MCPManager(MCPConfig.load(settings.mcp_config_path))
    await manager.start()
    outbox = OutboxStore(SessionLocal)
    outbox_worker = OutboxWorker(outbox, manager)
    outbox_task = asyncio.create_task(outbox_worker.run_forever())
    register_mcp_tools(manager, registry)
    checkpoint_context = TravelMindMySQLSaver.from_conn_string(
        settings.langgraph_database_url
    )
    checkpointer = await checkpoint_context.__aenter__()
    await checkpointer.setup()

    async def replan(job, trip, weather) -> str:  # type: ignore[no-untyped-def]
        runtime = getattr(app.state, "agent_runtime", None)
        if runtime is None:
            runtime = build_agent_runtime(
                registry=registry,
                checkpointer=checkpointer,
                memory_store=memory_store,
                task_store=task_store,
                skill_loader=skill_loader,
                events=events,
                knowledge_store=knowledge_store,
            )
            app.state.agent_runtime = runtime
        thread_id = job.thread_id or f"scheduler:trip:{trip.id}"
        result = await runtime.chat(
            "这是出发前自动天气复查。请根据以下真实天气判断原行程是否需要调整，并给出简洁替代建议；不要保存或执行外部写操作。"
            f"\n目的地：{trip.destination}\n天气：{weather}",
            AgentContext(
                user_id=job.user_id,
                thread_id=thread_id,
                channel="scheduler",
            ),
        )
        if job.thread_id and job.thread_id.startswith("feishu:"):
            chat_id = job.thread_id.removeprefix("feishu:")
            if chat_id and FEISHU_SEND_MESSAGE_TOOL in manager.tools:
                event = outbox.enqueue(
                    "mcp.call_tool",
                    {
                        "tool": FEISHU_SEND_MESSAGE_TOOL,
                        "arguments": feishu_text_arguments(
                            chat_id,
                            f"TravelMind 出发前天气复查：\n{result.message}",
                            f"weather-{job.id}",
                        ),
                    },
                    f"weather-notice:{job.id}",
                )
                await outbox_worker.dispatch(event.id)
        return result.message

    scheduler = Scheduler(SessionLocal, replan)
    scheduler_task = asyncio.create_task(scheduler.run_forever())
    app.state.tool_registry = registry
    app.state.mcp_manager = manager
    app.state.checkpointer = checkpointer
    app.state.feishu_events = EventDeduplicator(session_factory=SessionLocal)
    app.state.memory_store = memory_store
    app.state.task_store = task_store
    app.state.skill_loader = skill_loader
    app.state.events = events
    app.state.knowledge_store = knowledge_store
    app.state.outbox = outbox
    app.state.outbox_worker = outbox_worker
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler_task
        outbox_task.cancel()
        with suppress(asyncio.CancelledError):
            await outbox_task
        await manager.close()
        await checkpoint_context.__aexit__(None, None, None)


app = FastAPI(title="TravelMind", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def observe_request(request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id") or uuid4().hex
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    metrics = getattr(app.state, "http_metrics", None)
    if metrics is None:
        metrics = app.state.http_metrics = Counter()
    metrics["requests"] += 1
    metrics[f"status.{response.status_code}"] += 1
    logging.getLogger("travelmind.http").info(
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
            ensure_ascii=False,
        )
    )
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(api_router)
app.mount(
    "/ui",
    StaticFiles(directory=PROJECT_ROOT / "frontend", html=True),
    name="ui",
)
