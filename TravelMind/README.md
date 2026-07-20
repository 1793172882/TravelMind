# TravelMind

TravelMind 是一个面向真实出行场景的单 Agent 项目。它使用 LangChain/LangGraph 负责模型与工具循环，使用 Harness 统一管理工具、权限、审批、上下文、记忆、任务、恢复和 MCP Client，并通过 FastAPI 对外提供 Web 与飞书入口。

```text
用户 / 飞书
    ↓
FastAPI Controller
    ↓
Agent Runtime（LangChain + LangGraph）
    ↓
Harness（Registry → Permission → Interrupt → Recovery）
    ├── 本地工具
    └── MCP Client Manager → 飞书/地图/其他 MCP Server

Controller → Service → Repository → SQLAlchemy ORM → MySQL
```

## 当前已实现

- MySQL 行程与日程项 CRUD，严格遵循 Controller → Service → Repository 分层。
- LangChain `create_agent` 单 Agent 与 LangGraph Checkpoint。
- 基于 `thread_id` 的多轮对话、工具调用、人工审批、暂停与恢复。
- Harness Tool Registry、Pydantic 参数校验、权限分级、失败重试。
- 上下文压缩、用户偏好 Memory、依赖任务、Skill 按需加载的最小实现。
- 内置 MCP Manager，支持 stdio 和 Streamable HTTP；每个 Server 独立 Session 和故障隔离。
- MCP 工具动态发现并进入统一 Harness 权限管线。
- 飞书 Webhook challenge、token/签名校验、文本消息转换和事件去重。
- 无 Node 依赖的最小聊天/审批/行程演示页面。
- Fake MCP Server 与 24 个自动化测试（包含真实 stdio MCP 生命周期）。

当前是“可运行的后端 MVP”，不是所有外部服务都开箱即用。真实模型调用需要模型密钥；飞书写文档、日历等能力需要你提供可用的飞书 MCP Server；地图与天气能力建议后续以 MCP Server 接入。项目不会提交任何真实密钥。

## 目录职责

```text
backend/app/
├── api/                 # Controller、HTTP Schema、依赖组合
├── services/            # 业务流程和事务边界
├── domain/              # 纯业务模型与确定性约束
├── infrastructure/
│   ├── models/          # 一张表一个 SQLAlchemy ORM 文件/类
│   └── repositories/    # 数据库查询与写入
├── agent/               # 单 Agent 装配、Prompt、运行上下文
├── harness/             # 工具、权限、审批、恢复、记忆、任务、Skill
├── mcp/                 # 内置 MCP Client Manager 与工具适配
├── channels/            # 飞书等入站消息渠道
└── tools/               # 本地确定性工具
```

完整职责说明见 [项目结构与模块职责](docs/07-project-structure.md)，设计决策见 [详细架构设计](docs/02-architecture-design.md)。

## 1. 创建环境并安装

```powershell
conda create -n travelmind python=3.12 -y
conda activate travelmind
cd "C:\Users\he\Documents\learn harness\TravelMind\backend"
python -m pip install -e ".[dev]"
```

## 2. 配置 MySQL

在 MySQL 8.x 中执行 [schema.sql](backend/schema.sql)，然后复制环境变量模板：

```powershell
cd "C:\Users\he\Documents\learn harness\TravelMind"
Copy-Item .env.example .env
```

编辑 `.env` 中的 `DATABASE_URL`。示例：

```text
DATABASE_URL=mysql+pymysql://用户名:密码@127.0.0.1:3306/travelmind?charset=utf8mb4
```

## 3. 配置模型与 MCP

在 `.env` 填写 `MODEL_NAME`、`MODEL_API_KEY`，使用兼容 OpenAI 协议的第三方模型时再填写 `MODEL_BASE_URL`。

启用 MCP：

```powershell
Copy-Item config\mcp.example.json config\mcp.json
```

编辑 `config/mcp.json`，把目标 Server 的 `enabled` 改为 `true`。URL 与 Token 只填写在 `.env`，JSON 中只保存环境变量名。

## 4. 启动服务

```powershell
cd "C:\Users\he\Documents\learn harness\TravelMind\backend"
python -m uvicorn app.main:app --reload
```

打开：

- [健康检查](http://127.0.0.1:8000/health)
- [Swagger API 文档](http://127.0.0.1:8000/docs)
- [TravelMind 演示界面](http://127.0.0.1:8000/ui/)

核心接口：

```text
POST /chat
GET  /approvals/{thread_id}
POST /approvals/{thread_id}
POST /trips
GET  /trips
GET  /trips/{trip_id}
POST /trips/{trip_id}/items
GET  /trips/{trip_id}/items
POST /trips/{trip_id}/archive
POST /webhooks/feishu
```

## 5. 运行验收

```powershell
cd backend
python -m ruff check app tests
python -m pytest -q
```

若 Windows 沙箱禁止创建子进程，只有真实 stdio MCP 测试会出现 `WinError 5`；在普通终端运行即可。

## 当前边界

- Checkpoint 目前使用进程内 `InMemorySaver`，服务重启恢复需要下一阶段换成 MySQL Checkpointer。
- 飞书 Webhook 已能把消息交给 Agent；将结果主动回复飞书，需要启用提供发消息工具的飞书 MCP Server。
- `tools/amap.py`、`tools/weather.py`、持久 Outbox 和 Scheduler 尚未接真实服务，避免在没有 API/MCP 选择和凭证时伪造“已集成”。
- 第一版不做自动付款、抢票、非官方个人微信登录、多 Agent、微服务、Redis或向量数据库。

## 文档导航

1. [产品需求文档](docs/01-product-requirements.md)
2. [详细架构设计](docs/02-architecture-design.md)
3. [Harness 与 MCP 设计](docs/03-harness-and-mcp-design.md)
4. [实现流程与里程碑](docs/04-implementation-roadmap.md)
5. [项目驱动学习路线](docs/05-project-learning-guide.md)
6. [数据模型、接口与测试](docs/06-data-api-testing.md)
7. [项目结构与模块职责](docs/07-project-structure.md)
