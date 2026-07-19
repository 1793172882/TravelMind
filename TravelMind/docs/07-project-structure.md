# 项目结构与模块职责

这份文档回答三个问题：代码放在哪里、这个模块负责什么、应该在哪个阶段实现。骨架中的占位模块目前只有职责说明，不代表功能已经完成。

## 1. 完整目录树

```text
TravelMind/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── router.py
│   │   │   └── routes/
│   │   │       ├── health.py
│   │   │       ├── chat.py
│   │   │       ├── approvals.py
│   │   │       ├── trips.py
│   │   │       └── webhooks.py
│   │   ├── agent/
│   │   │   ├── runtime.py
│   │   │   ├── graph.py
│   │   │   ├── state.py
│   │   │   └── prompts.py
│   │   ├── harness/
│   │   │   ├── tool_registry.py
│   │   │   ├── permissions.py
│   │   │   ├── middleware.py
│   │   │   ├── context.py
│   │   │   ├── memory.py
│   │   │   ├── tasks.py
│   │   │   ├── skills.py
│   │   │   ├── recovery.py
│   │   │   └── scheduler.py
│   │   ├── mcp/
│   │   │   ├── manager.py
│   │   │   ├── config.py
│   │   │   └── tool_adapter.py
│   │   ├── domain/
│   │   │   ├── models.py
│   │   │   └── constraints.py
│   │   ├── tools/
│   │   │   ├── budget.py
│   │   │   ├── amap.py
│   │   │   └── weather.py
│   │   ├── channels/
│   │   │   └── feishu.py
│   │   └── infrastructure/
│   │       ├── database.py
│   │       ├── repositories.py
│   │       └── outbox.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── e2e/
│   │   └── test_health.py
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── api/
│       ├── components/
│       └── features/
│           ├── chat/
│           ├── trips/
│           └── approvals/
├── skills/
├── config/
│   └── mcp.example.json
├── docs/
├── .env.example
├── .gitignore
└── README.md
```

## 2. 依赖规则

代码依赖必须遵守：

```text
API / Channel
      ↓
Agent Runtime / Application Flow
      ↓
Harness ─────────→ MCP
      ↓              ↓
Domain          Infrastructure
```

更具体的规则：

- `domain` 不得导入 FastAPI、LangChain、LangGraph、MCP或数据库客户端。
- `tools` 可以调用外部API，但返回 `domain` 模型或精简字典。
- `agent` 可以使用 `harness`、`domain` 和 `tools`。
- `api` 只负责协议转换，不写Prompt、约束规则或MCP连接逻辑。
- `mcp` 不直接决定权限；它只连接Server和执行调用。
- `harness.permissions` 是所有本地工具和MCP工具的统一安全入口。
- `infrastructure` 实现数据库和外部持久化，不决定业务流程。

## 3. 根目录

### `README.md`

用途：新人入口、启动命令、文档索引和当前项目状态。

每完成一个里程碑，应更新“当前可运行能力”，不要把未来功能写成已经完成。

### `.env.example`

用途：列出需要的环境变量名称和注释，不保存真实值。

未来可能包括：

```text
MODEL_PROVIDER
MODEL_NAME
MODEL_API_KEY
DATABASE_URL
AMAP_API_KEY
FEISHU_APP_ID
FEISHU_APP_SECRET
```

只有真正使用某项集成时才增加变量。

### `config/mcp.example.json`

用途：展示可配置MCP Server格式。

只保存：Server名称、Transport、命令或URL、环境变量名称。禁止保存Token。

## 4. `backend/app/main.py`

这是应用组合根，只负责：

- 创建FastAPI实例。
- 注册路由。
- 后续注册lifespan。
- lifespan中启动数据库、MCP Manager和Scheduler。
- 退出时关闭连接。

禁止放入：

- 业务规则。
- Prompt。
- 工具实现。
- 数据库查询。

当前已经能够启动并提供 `/health`。

## 5. API层

### `api/router.py`

集中注册所有FastAPI Router。新增业务接口时在这里挂载，不在 `main.py` 中不断堆接口。

### `api/routes/health.py`

当前已实现。用于进程存活检查，不访问外部服务。

未来增加 `/ready` 时才检查数据库和必要MCP连接。

### `api/routes/chat.py`

阶段1和阶段9实现。

职责：

- 接收用户消息、`thread_id`和渠道信息。
- 创建 `AgentContext`。
- 调用Agent Runtime。
- 将流式事件转换为稳定SSE协议。

禁止直接调用高德或飞书。

### `api/routes/approvals.py`

阶段4实现。

职责：

- 查询当前等待审批的操作。
- 接收 `approve/edit/reject`。
- 构造LangGraph `Command(resume=...)`。
- 使用原 `thread_id` 恢复执行。

### `api/routes/trips.py`

阶段3和阶段8实现。

职责：查询已保存行程、触发重规划、归档行程。具体校验放在Domain，持久化放在Repository。

### `api/routes/webhooks.py`

阶段7实现。

职责：

- 验证飞书回调签名。
- 处理URL验证。
- 通过事件ID去重。
- 将消息交给Channel Adapter。
- 快速返回，耗时Agent执行进入后台。

## 6. Agent层

### `agent/runtime.py`

阶段1开始实现，是单Agent的装配位置。

负责调用LangChain v1 `create_agent`，注入：

```text
model
tools
system_prompt
middleware
state_schema
context_schema
response_format
checkpointer/store
```

这里不手写另一套模型—工具 `while` 循环。

未来多Agent时，保留当前 `travel_agent`，再增加Agent Registry；各Agent仍复用Harness。

### `agent/graph.py`

阶段4开始实现。

负责出行任务外层生命周期：

```text
Agent交互
→ 约束校验
→ 人工审批
→ 外部同步
→ 定时监测
→ 动态重规划
```

不要把模型的每一次推理写成Graph Node。Graph只表达需要持久化、审批或恢复的业务边界。

### `agent/state.py`

已经提供基础结构：

- `AgentContext`：本次调用环境，不作为对话消息保存。
- `TravelAgentState`：LangGraph需要Checkpoint的执行状态。

未来新增字段前先问：它是执行状态、业务数据还是长期记忆？业务数据应进入Trip表，长期偏好应进入Memory Store。

### `agent/prompts.py`

阶段1和阶段5实现。

负责动态组合：

```text
稳定安全规则
出行Agent角色
当前时间与地点
用户偏好摘要
已加载Skill
可用工具提示
```

Prompt不保存任务状态，也不拼入密钥。

## 7. Harness层

### `harness/tool_registry.py`

阶段1和阶段6实现。

这是工具唯一目录，统一管理：

- 本地Python工具。
- REST API工具。
- MCP动态发现工具。
- 工具名称空间。
- Risk Level和可用状态。
- 根据 `agent_id` 过滤工具。

模型只看到经过Registry和Permission过滤后的工具。

### `harness/permissions.py`

阶段4实现，当前已有 `PermissionDecision`。

输入：用户、Agent、工具名、风险等级和参数摘要。

输出：

```text
ALLOW
ASK
DENY
```

该模块不执行工具，只给出决策。

### `harness/middleware.py`

阶段4和阶段5实现。

使用LangChain v1 Middleware实现：

- 模型调用前注入Memory和Skill。
- 模型调用前触发Context Compact。
- Tool Call前做Schema与权限检查。
- Tool Call后清洗结果和记录审计。
- Tool异常时调用Recovery Policy。

### `harness/context.py`

阶段5实现。

负责控制上下文体积，按顺序：裁剪重复结果、压缩工具输出、总结历史。必须保留硬约束、待审批操作和未完成任务。

### `harness/memory.py`

阶段5实现。

负责用户长期偏好的Selection、Extraction和Consolidation，例如最大步行距离、饮食限制和交通偏好。

不保存每一句聊天，也不在第一版引入向量数据库。

### `harness/tasks.py`

阶段5实现。

负责Todo和持久任务：

```text
task_id
parent_id
blocked_by
status
result
agent_id
```

当前所有Task由 `travel_agent` 执行；未来多Agent可以在不改Task结构的情况下领取任务。

### `harness/skills.py`

阶段5实现。

启动时只发现Skill名称和描述；Agent明确需要时才加载完整 `SKILL.md`，避免把所有领域知识塞入Prompt。

### `harness/recovery.py`

阶段5实现。

将错误分类为超时、限流、参数错误、MCP断线、上下文过长和外部写入失败，再选择有上限重试、重连、回到模型、降级或Outbox。

### `harness/scheduler.py`

阶段8实现。

负责注册：出发前天气检查、路线检查、待同步重试和行程归档。调度任务必须持久化并且操作幂等。

## 8. MCP层

### `mcp/manager.py`

阶段6实现，是内置MCP Host核心。

职责：

- 为每个Server维护一个Client Session。
- 在应用启动时连接、`initialize`、`list_tools`。
- 将工具交给Adapter和Tool Registry。
- 调用 `call_tool`。
- 单Server断线重连。
- 应用关闭时清理全部Session。

这里不保存业务状态，也不做权限决策。

### `mcp/config.py`

阶段6实现。

将 `mcp.json` 解析为受验证配置，解析stdio和Streamable HTTP参数。Token通过环境变量读取，但不能进入可序列化配置或Prompt。

### `mcp/tool_adapter.py`

阶段6实现。

负责：

- `server + remote_tool` 转换成命名空间名称。
- MCP JSON Schema转换为LangChain Tool Schema。
- MCP结果转换成模型可消费的短结果。
- 保留来源Server和原始工具名用于审计。

## 9. Domain层

### `domain/models.py`

当前已经提供第一批Pydantic模型：

- `TripRequirement`
- `ItineraryItem`
- `Itinerary`

这些模型同时用于结构化输出、API响应和约束检查，避免维护三套相同数据结构。

### `domain/constraints.py`

阶段3实现，是项目正确性的核心。

使用普通Python校验：

- 时间区间和重叠。
- 路线时间是否足够。
- 总预算。
- 总步行距离。
- 营业时间。

这些规则必须有单元测试，不依赖LLM。

## 10. Native Tools层

### `tools/budget.py`

阶段1的第一个工具。使用Decimal计算总费用和剩余预算，用它学习Tool Calling完整链路。

### `tools/amap.py`

阶段2实现。封装地理编码、POI和路线接口；只返回项目需要的精简字段、来源和查询时间。

### `tools/weather.py`

阶段2实现。封装天气查询并标准化天气现象、温度、降水和预警。

这些工具最终与MCP工具一起进入Tool Registry。

## 11. Channel层

### `channels/feishu.py`

阶段7实现。它解决“飞书如何把用户消息交给Agent”，不是MCP Client替代品。

职责：回调验证、消息解析、平台用户映射和响应格式转换。

飞书MCP则解决“Agent如何创建文档和日历”。两者方向不同：

```text
飞书Webhook → Channel → Agent
Agent → MCP Client → 飞书MCP Server
```

未来微信、企业微信等入口在 `channels/` 增加适配器；外部能力仍通过MCP接入。

## 12. Infrastructure层

### `infrastructure/database.py`

阶段4实现。负责PostgreSQL连接、LangGraph Postgres Checkpointer/Store和应用生命周期。

### `infrastructure/repositories.py`

阶段5实现。保存Trip、Task、UserPreference和ToolAudit。不要在Repository中调用LLM。

### `infrastructure/outbox.py`

阶段7实现。外部写入失败时保存事件，由后台任务重试；使用幂等键防止重复创建飞书文档和日历。

## 13. 测试目录

### `tests/unit`

不连接网络和真实数据库，测试约束、权限、Schema、工具结果转换和Memory合并。

### `tests/integration`

测试PostgreSQL Checkpoint、Fake MCP Server、高德录制响应和飞书测试应用。

### `tests/e2e`

从用户消息开始，验证工具轨迹、审批、行程保存和外部同步完整流程。

### `test_health.py`

当前最小烟雾测试，保证FastAPI应用可以导入和响应。

## 14. 前端目录

前端阶段9实现：

- `src/api`：HTTP与SSE Client。
- `src/components`：无业务状态的通用组件。
- `features/chat`：聊天与执行轨迹。
- `features/trips`：行程时间轴和地图。
- `features/approvals`：审批卡片。

在阶段9之前不安装Node依赖，避免前后端同时开工分散学习目标。

## 15. Skills目录

阶段5逐个创建：

```text
skills/family-trip/SKILL.md
skills/budget-trip/SKILL.md
skills/bad-weather-replan/SKILL.md
```

Skill是按需知识，不是Python插件，也不能绕过Tool Registry和Permission Engine。

## 16. 你应该从哪里开始

严格按照以下文件顺序实现，不要同时填写所有占位模块：

```text
1. tools/budget.py
2. harness/tool_registry.py
3. agent/runtime.py
4. api/routes/chat.py
5. tools/weather.py + tools/amap.py
6. domain/constraints.py
7. agent/graph.py
8. harness/permissions.py + middleware.py
9. infrastructure/database.py
10. mcp/config.py + manager.py + tool_adapter.py
11. channels/feishu.py + infrastructure/outbox.py
12. context.py + memory.py + tasks.py + skills.py
13. scheduler.py
14. frontend
```

每完成一步，都需要：一个可运行演示、一个最小测试、一次文档更新。详细验收条件见 [实现流程与里程碑](04-implementation-roadmap.md)。

## 17. 多 Agent扩展位置

当前没有子Agent代码。未来扩展时：

```text
app/agents/registry.py        注册多个Agent
app/agents/supervisor.py      分解和分派任务
app/agents/protocol.py        Agent间消息结构
```

不会复制MCP Manager、Permission Engine、Memory或Task System。子Agent作为工具或Subgraph接入现有LangGraph，并继承父图Checkpoint命名空间。

只有当单Agent出现可测量问题时才创建这些文件。

