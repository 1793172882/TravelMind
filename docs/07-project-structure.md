# 项目结构与模块职责

## 1. 当前目录树

```text
TravelMind/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   ├── dependencies.py
│   │   │   ├── routes/
│   │   │   │   ├── health.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── chat.py
│   │   │   │   ├── approvals.py
│   │   │   │   ├── trips.py
│   │   │   │   ├── automations.py
│   │   │   │   └── webhooks.py
│   │   │   └── schemas/
│   │   │       ├── auth.py
│   │   │       ├── chat.py
│   │   │       └── trips.py
│   │   ├── services/
│   │   │   ├── auth.py
│   │   │   └── trip.py
│   │   ├── domain/
│   │   │   ├── models.py
│   │   │   └── constraints.py
│   │   ├── agent/
│   │   │   ├── runtime.py
│   │   │   ├── prompts.py
│   │   │   ├── state.py
│   │   │   └── graph.py
│   │   ├── harness/
│   │   │   ├── tool_registry.py
│   │   │   ├── permissions.py
│   │   │   ├── middleware.py
│   │   │   ├── runtime_context.py
│   │   │   ├── context.py
│   │   │   ├── memory.py
│   │   │   ├── tasks.py
│   │   │   ├── skills.py
│   │   │   ├── recovery.py
│   │   │   ├── events.py
│   │   │   └── scheduler.py
│   │   ├── tools/
│   │   │   ├── budget.py
│   │   │   ├── itinerary.py
│   │   │   ├── trips.py
│   │   │   ├── amap.py
│   │   │   └── weather.py
│   │   ├── mcp/
│   │   │   ├── config.py
│   │   │   ├── manager.py
│   │   │   ├── tool_adapter.py
│   │   │   └── feishu_auth.py
│   │   ├── channels/
│   │   │   └── feishu.py
│   │   └── infrastructure/
│   │       ├── database.py
│   │       ├── checkpoint.py
│   │       ├── outbox.py
│   │       ├── models/          # 一张业务表一个 ORM 文件
│   │       └── repositories/    # trip、itinerary_item
│   ├── evals/travel_cases.json
│   ├── scripts/
│   │   ├── check_mcp.py
│   │   └── evaluate.py
│   ├── tests/
│   ├── schema.sql
│   └── pyproject.toml
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── config/mcp.example.json
├── skills/
│   ├── budget-travel/SKILL.md
│   └── family-travel/SKILL.md
├── docs/
├── .env.example
├── .gitignore
└── README.md
```

## 2. 依赖规则

```text
API / Channel
      ↓
Service 或 Agent Runtime
      ↓
Harness / Domain
      ↓
Repository / Tool / MCP
      ↓
MySQL / 外部服务
```

- Controller 不直接使用 SQLAlchemy Engine 或 Session 查询。
- Service 控制业务流程、commit 和 rollback。
- Repository 不 commit，只操作 ORM。
- Domain 不依赖框架和外部服务。
- Agent 不直接绕过 Harness 调用 MCP。
- MCP Adapter 不决定业务权限，Risk Level 仍由 Harness 执行。

## 3. 根目录文件

### `README.md`

项目入口：当前能力、安装、配置、启动、API、测试、边界和文档导航。

### `.env.example`

列出 MySQL、千问、高德、鉴权和飞书配置名。真实 `.env` 被 `.gitignore` 排除。

### `config/mcp.example.json`

提供 Fake MCP、飞书远程 MCP、官方 `lark-mcp` 三类配置示例。本地启用配置复制为 `config/mcp.json`，该文件不会提交。

## 4. 应用组合

### `app/main.py`

唯一组合根：

- 创建 FastAPI 并注册 `api_router`。
- 挂载 `/ui` 静态页面。
- lifespan 创建业务表、Store、Registry、MCP、Checkpoint、Scheduler 和 Outbox Worker。
- 定义天气复查调用 Agent 和飞书通知的组合逻辑。
- 记录请求 ID、状态码和耗时。

这里可以组合对象，但不应加入新的行程 SQL 或大段 Prompt。

### `app/config.py`

Pydantic Settings；仓库根目录由 `Path(__file__).parents[2]` 计算，所以移动工作目录不会改变 `.env`、`skills`、`config/mcp.json` 的定位。

## 5. API 层

### `api/router.py`

集中注册全部 Router。项目 API 没有 `/api` 前缀。

### `api/dependencies.py`

组合请求级数据库 Session、当前用户、TripService 和共享 Agent Runtime。身份隔离也在这里进入 Service/Runtime。

### `api/routes/health.py`

`/health`、`/version`、`/metrics`、`/integrations`。

### `api/routes/auth.py`

注册、登录、查询当前身份；只调用 `AuthService`。

### `api/routes/chat.py`

聊天、历史、SSE 和事件快照。构造 `AgentContext` 后调用 Runtime，不直接调用高德、数据库或 MCP。

### `api/routes/approvals.py`

查询 LangGraph interrupt，并以 approve/reject 恢复相同线程。

### `api/routes/trips.py`

行程和日程 CRUD、归档、静态地图。数据库操作全部通过 `TripService`；地图通过高德工具生成。

### `api/routes/automations.py`

查询当前用户 Scheduler Job，并可手动运行已到期任务。

### `api/routes/webhooks.py`

飞书入站边界：验证、去重、后台执行 Agent、处理飞书审批回复，并通过 Outbox 回复消息。

### `api/schemas/*`

HTTP 信任边界。负责字符串长度、金额非负、状态枚举、请求/响应序列化。

## 6. Service 与数据访问

### `services/auth.py`

PBKDF2 密码哈希、HMAC Token、注册登录、Token 解析和身份模型。

### `services/trip.py`

行程业务和事务边界：

- 创建、查询、更新、删除、归档。
- 日程项 CRUD。
- 行程与全部日程一次提交。
- 创建/修改开始时间时更新天气 Job。
- 删除/归档时取消 Job。

### `infrastructure/repositories/trip.py`

所有查询都包含 `owner_id`，保证用户隔离。

### `infrastructure/repositories/itinerary_item.py`

按 `trip_id/day_number/sort_order` 查询，处理日程增删。

### `infrastructure/models/*`

一张业务表一个 SQLAlchemy 类：

```text
user.py                 users
trip.py                 trips
itinerary_item.py       itinerary_items
user_preference.py      user_preferences
harness_task.py         harness_tasks
webhook_event.py        webhook_events
outbox_event.py         outbox_events
scheduled_job.py        scheduled_jobs
```

## 7. Domain 层

### `domain/models.py`

`TripRequirement`、`Itinerary`、领域 `ItineraryItem`，用于 Agent 嵌套参数和约束校验。它与 ORM 的 `ItineraryItem` 同名但用途不同。

### `domain/constraints.py`

纯 Python 硬约束：时间、范围、重叠、预算、步行和必去地点。没有网络和数据库依赖。

## 8. Agent 层

### `agent/runtime.py`

项目的单 Agent 核心：

- 构建本地 Registry。
- 把 Harness 工具转成 LangChain StructuredTool。
- 组装模型、动态 Prompt、摘要 Middleware 和 Checkpointer。
- 提供聊天、审批恢复和历史读取。

### `agent/prompts.py`

稳定业务规则，不保存用户状态或凭证。

### `agent/state.py`

`AgentContext` 正在使用；`TravelAgentState` 为未来外层业务图预留，当前未接入。

### `agent/graph.py`

当前只有说明，没有额外业务 Graph。不要把它描述成已经实现的 Trip Lifecycle。

## 9. Harness 层

### `tool_registry.py`

唯一工具目录、名称唯一检查、Pydantic 参数验证和 handler 分发。

### `permissions.py` 与 `middleware.py`

前者只做 ALLOW/ASK/DENY 决策；后者连接事件、审批、有限重试和真实工具执行。

### `runtime_context.py`

使用 `ContextVar` 在深层工具调用中取得当前用户、线程和 Agent，不把这些参数暴露给模型。

### `memory.py`

结构化偏好读取和合并，可在测试中使用内存实现，在应用中使用 MySQL。

### `tasks.py`

依赖任务创建、列表、runnable 计算和完成，可使用内存或 MySQL Store。

### `skills.py`

发现 Skill 元数据并按名称延迟加载完整 `SKILL.md`。

### `context.py`

确定性消息裁剪辅助函数；生产长会话摘要由 Agent Runtime 的官方 Middleware 完成。

### `recovery.py`

针对 Timeout/ConnectionError 的通用异步有限重试。

### `events.py`

单进程 EventBroker：SSE 重连缓冲、线程订阅和事件计数。不是持久审计系统。

### `scheduler.py`

MySQL 天气 Job 的创建、取消、查询、到期扫描、失败计数和结果保存。

## 10. Native Tools

### `tools/budget.py`

Decimal 预算合计、余额和超支判断。

### `tools/itinerary.py`

把领域约束包装为 Agent 工具。

### `tools/trips.py`

Agent 使用的数据库工具，但仍只通过 `TripService` 访问数据库。

### `tools/amap.py`

高德请求基础、地理编码、POI、路线和静态地图，负责错误归一化与结果压缩。

### `tools/weather.py`

高德天气当前/预报响应标准化。

## 11. MCP 层

### `mcp/config.py`

验证 Server transport、URL/Token 环境变量、stdio 命令和 `env_from`。

### `mcp/manager.py`

每个 Server 一个 Session，负责连接、发现、调用和关闭；连接错误彼此隔离。

### `mcp/tool_adapter.py`

把 MCP JSON Schema 转成 Pydantic Model，添加 Server 命名空间并推断 Risk Level。

### `mcp/feishu_auth.py`

飞书 tenant token 获取、两小时缓存和远程 MCP 请求头。

## 12. Channel 与 Outbox

### `channels/feishu.py`

飞书回调签名和 token 验证、文本事件解析、线程映射、事件去重和消息请求参数构造。

### `infrastructure/outbox.py`

持久 MCP 调用、幂等键、指数退避和后台分发。当前主要保护飞书回复和天气通知。

## 13. 前端

前端实际实现集中在三个文件：

- `index.html`：仪表盘、助手、行程、登录和详情抽屉结构。
- `styles.css`：响应式视觉、状态、组件和移动端布局。
- `app.js`：HTTP/SSE、认证状态、审批、行程 CRUD、日程编辑和地图加载。

`frontend/src/*` 目前只有 `.gitkeep`，不代表已经存在 React/Vue 模块。项目刻意不使用 Node 构建工具和前端框架。

## 14. 评测与测试

### `evals/travel_cases.json`

100 条真实 Agent 输入和可观察预期。

### `scripts/evaluate.py`

调用运行中的 API，读取每线程工具事件，计算指标并输出 Markdown 报告。

### `scripts/check_mcp.py`

安全检查启用的 MCP Server、工具数量和错误，不输出 Token。

### `tests/*`

当前测试按能力拆成 11 个 `test_*.py`，总计 40 项。`unit/integration/e2e` 子目录目前是预留空目录，实际测试仍平铺在 `tests/`。

## 15. Skills

当前两个 Skill 已被运行时发现：

```text
skills/budget-travel/SKILL.md
skills/family-travel/SKILL.md
```

Skill 不能调用数据库或外部服务，也不能改变工具风险等级。

## 16. 推荐阅读顺序

```text
1. main.py + api/router.py
2. api/routes/trips.py → services/trip.py → repositories
3. tools/budget.py → tool_registry.py → agent/runtime.py
4. permissions.py → middleware.py → approvals.py → checkpoint.py
5. domain/constraints.py → tools/trips.py
6. memory.py → tasks.py → skills.py
7. mcp/config.py → manager.py → tool_adapter.py
8. channels/feishu.py → webhooks.py → outbox.py
9. scheduler.py → main.py 的 replan
10. scripts/evaluate.py + 100 条评测
```

每读完一条链路，运行对应测试并画出数据流；不要一次背完整目录。
