# TravelMind

TravelMind 是一个以项目驱动方式学习 Agent 工程的智慧出行助手。当前采用单 Agent，围绕它实现完整 Harness：工具、权限、Hooks、计划、Skill、上下文压缩、记忆、错误恢复、持久化任务、后台任务、定时任务和内置 MCP Client；未来再扩展为多 Agent。

## 项目目标

用户可以从 Web 或飞书提出真实出行需求，例如：

> 周六带父母从上海去杭州一日游，预算 1500 元，尽量少走路；如果下雨，请调整行程并同步到飞书。

系统需要完成：

1. 澄清缺失条件。
2. 查询地点、天气和路线。
3. 生成结构化行程。
4. 用确定性代码校验时间、距离和预算。
5. 在外部写入前请求用户审批。
6. 将行程同步到飞书文档、日历或多维表格。
7. 定时监测变化并重新规划。
8. 在服务重启后恢复未完成任务。

## 核心公式

```text
Agent = LLM + Harness

LLM：理解、推理、规划、选工具、判断结束
Harness：工具、知识、上下文、状态、权限、执行与恢复
```

## 架构原则

- LangChain `create_agent` 承担模型—工具循环，不重复实现第二套 Agent Loop。
- LangGraph承担持久执行、Checkpoint、Memory、Interrupt和任务恢复。
- Harness内置 MCP Manager，每个 MCP Server对应独立 Client Session。
- 本地工具与 MCP 工具进入同一个 Tool Registry和权限管线。
- 大模型负责语义理解，普通代码负责金额、时间、距离等确定性校验。
- 当前不创建子 Agent；出现明确的上下文、工具或并发瓶颈后再拆分。

## 文档导航

1. [产品需求文档](docs/01-product-requirements.md)
2. [详细架构设计](docs/02-architecture-design.md)
3. [Harness 与 MCP 设计](docs/03-harness-and-mcp-design.md)
4. [实现流程与里程碑](docs/04-implementation-roadmap.md)
5. [项目驱动学习路线](docs/05-project-learning-guide.md)
6. [数据模型、接口与测试](docs/06-data-api-testing.md)
7. [项目结构与模块职责](docs/07-project-structure.md)

## 推荐阅读顺序

第一次阅读按 `01 → 07` 顺序。开始编码后，以 [实现流程与里程碑](docs/04-implementation-roadmap.md) 为主线；不知道代码应放在哪里时，查看 [项目结构与模块职责](docs/07-project-structure.md)。

## 项目结构

```text
TravelMind/
├── backend/
│   ├── app/
│   │   ├── api/             # HTTP与Webhook入口
│   │   ├── agent/           # 单Agent装配和LangGraph生命周期
│   │   ├── harness/         # 工具、权限、记忆、任务、恢复
│   │   ├── mcp/             # 内置MCP Host与多个Client Session
│   │   ├── domain/          # 出行模型和确定性约束
│   │   ├── tools/           # 高德、天气、预算等本地工具
│   │   ├── channels/        # 飞书等消息渠道适配
│   │   └── infrastructure/  # PostgreSQL、仓储和Outbox
│   ├── tests/
│   └── pyproject.toml
├── frontend/src/
├── skills/
├── config/
└── docs/
```

## 当前技术选型

| 领域 | 选择 |
|---|---|
| 语言 | Python 3.12 |
| Agent | LangChain 1.x |
| Runtime | LangGraph 1.x |
| MCP | 官方 MCP Python SDK |
| API | FastAPI |
| 数据校验 | Pydantic 2 |
| HTTP | HTTPX |
| 数据库 | PostgreSQL |
| 调度 | APScheduler |
| 前端 | React + TypeScript + Vite |
| 测试与质量 | pytest + Ruff |
| 本地部署 | Docker Compose |

## 当前可运行骨架

先创建并激活你自己的 Conda 环境，然后安装和运行：

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000/health`，预期返回：

```json
{"status":"ok","service":"TravelMind"}
```

运行检查：

```powershell
python -m pytest
python -m ruff check .
```

## 非目标

第一版不实现自动订票、付款、非官方个人微信协议、多 Agent、微服务、Celery、Redis和向量数据库。这些能力只有在真实需求出现时才加入。
