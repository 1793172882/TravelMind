# 数据模型、API 与测试

## 1. 数据模型分层

项目有三类“模型”，用途不同：

| 类型 | 位置 | 用途 |
|---|---|---|
| API Schema | `app/api/schemas` | 校验 HTTP 请求和序列化响应 |
| Domain Model | `app/domain/models.py` | 候选行程和确定性约束 |
| ORM Model | `app/infrastructure/models` | 映射 MySQL 表 |

不要把 ORM 对象直接作为 Agent State，也不要让 Repository 接收 HTTP Request。

## 2. Domain Model

### `TripRequirement`

```text
destination
start_at
end_at
budget                    可选，Decimal >= 0
max_walking_distance_m    可选，整数 >= 0
must_visit                字符串列表
```

### `ItineraryItem`

```text
title
location
start_at
end_at
estimated_cost            Decimal，默认 0
walking_distance_m        整数，默认 0
source                    可选
```

### `Itinerary`

```text
items: list[ItineraryItem]
```

领域校验实际覆盖：整体时间合法、日程时间合法、超出范围、时间重叠、预算、步行距离和必去地点。

## 3. MySQL 表

项目使用逻辑外键，不创建数据库 `FOREIGN KEY`。行程所有权通过查询条件控制，日程删除由 Service 协调。

### `users`

```text
id               BIGINT 主键
username         唯一用户名
password_hash    PBKDF2 密码摘要
created_at
```

### `trips`

```text
id
owner_id         anonymous / web:{id} / feishu:{open_id}
thread_id        可选，创建行程的 Agent 会话
origin
destination
start_at/end_at  MySQL DATETIME，可空
budget           DECIMAL(10,2)，可空
status           draft / active / completed / archived
created_at/updated_at
```

### `itinerary_items`

```text
id
trip_id          逻辑外键
day_number
sort_order
title
location
start_at/end_at
estimated_cost
source
created_at
```

### `user_preferences`

```text
user_id                    主键
max_walking_distance_m
preferred_transport        JSON 数组
dietary_restrictions       JSON 数组
travels_with_elderly
updated_at
```

### `harness_tasks`

```text
task_id                    字符串主键
user_id/thread_id
description
blocked_by                 JSON 数组
status                     pending/running/completed/failed
result
agent_id                   默认 travel_agent
created_at/updated_at
```

### `webhook_events`

保存 `event_id` 和 `expires_at`，阻止飞书重复回调重复执行。

### `outbox_events`

保存 MCP 调用主题、参数、唯一幂等键、状态、尝试次数、下次执行时间和最后错误。最多重试 5 次。

### `scheduled_jobs`

保存行程的 `weather_24h`、`weather_2h` 任务、运行时间、状态、尝试次数、天气/建议结果和错误。

### LangGraph 表

Checkpoint 表由 `langgraph-checkpoint-mysql` 创建。`TravelMindMySQLSaver` 只调整官方迁移 SQL，以兼容 MySQL 8.0.12 不允许 JSON 默认值的限制。

## 4. 数据库初始化

首次可手动执行 `backend/schema.sql`。应用启动时 `Base.metadata.create_all()` 会创建缺少的业务表，并为早期 `trips` 表增量补充 `owner_id/thread_id`。

当前没有 Alembic。后续若频繁修改生产表结构，再引入版本化迁移；本地简历项目不需要额外迁移框架。

## 5. 鉴权与用户隔离

### 注册

```http
POST /auth/register
Content-Type: application/json

{"username":"traveler","password":"至少8个字符"}
```

### 登录

```http
POST /auth/login
```

返回 HMAC 签名 Bearer Token。使用：

```http
Authorization: Bearer <access_token>
```

`GET /auth/me` 返回当前身份。`AUTH_REQUIRED=false` 时没有 Token 的请求使用匿名身份；设为 `true` 后强制登录。

行程 Repository 按 `owner_id` 查询；Checkpoint thread 同样包含用户前缀，避免不同用户使用相同前端 `thread_id` 时串线。

## 6. Chat 与审批 API

### 对话

```http
POST /chat
Content-Type: application/json

{
  "message": "查询杭州天气并规划一日游",
  "thread_id": "hangzhou-001",
  "channel": "web"
}
```

响应：

```json
{
  "thread_id": "hangzhou-001",
  "message": "...",
  "status": "completed",
  "pending_approvals": []
}
```

写工具暂停时 `status` 为 `waiting_approval`。

### 历史与事件

```text
GET /chat/{thread_id}/history          用户/Agent 可见消息
GET /chat/{thread_id}/events           持续 SSE
GET /chat/{thread_id}/events/snapshot  当前内存缓冲事件，用于诊断/评测
```

当前稳定事件：

```text
run.started
run.completed
run.paused
tool.started
tool.completed
tool.failed
tool.rejected
approval.required
approval.decided
```

### 审批

```text
GET  /approvals/{thread_id}
POST /approvals/{thread_id}
```

```json
{"decision":"approve","channel":"web"}
```

`decision` 只支持 `approve`、`reject`，当前不支持在审批接口直接编辑工具参数。

## 7. 行程 API

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/trips/preview` | 校验最小输入并返回规划提示 |
| POST | `/trips` | 创建行程 |
| GET | `/trips` | 当前用户行程列表 |
| GET | `/trips/{trip_id}` | 行程详情 |
| PATCH | `/trips/{trip_id}` | 更新行程字段 |
| DELETE | `/trips/{trip_id}` | 删除行程及逻辑关联日程 |
| POST | `/trips/{trip_id}/archive` | 归档并取消天气任务 |
| POST | `/trips/{trip_id}/items` | 新增日程项 |
| GET | `/trips/{trip_id}/items` | 按天/顺序读取日程 |
| PATCH | `/trips/{trip_id}/items/{item_id}` | 更新日程项 |
| DELETE | `/trips/{trip_id}/items/{item_id}` | 删除日程项 |
| GET | `/trips/{trip_id}/map` | 返回高德静态 PNG |

创建示例：

```json
{
  "origin": "上海",
  "destination": "杭州",
  "start_at": "2026-10-01T09:00:00",
  "end_at": "2026-10-01T21:00:00",
  "budget": "1500.00",
  "thread_id": "hangzhou-001"
}
```

HTTP CRUD 不自动调用 Agent。自然语言规划和 `trip.save_itinerary` 是另一条 Agent 工具链，两者最终复用同一个 `TripService`。

## 8. 自动任务、Webhook 与运维 API

```text
GET  /automations       当前用户天气任务
POST /automations/run   手动运行已经到期的任务
POST /webhooks/feishu   飞书事件入口

GET /health             进程健康
GET /version            应用版本
GET /metrics            HTTP 计数与 Agent 事件计数
GET /integrations       千问/高德/飞书/MCP 配置状态
```

`/health` 只表示进程存活；外部集成是否就绪应查看 `/integrations`。当前没有单独 `/ready`。

## 9. 自动化测试

当前 pytest 共 40 项，覆盖：

- FastAPI、静态 UI、请求 Schema 和 Webhook lifespan。
- Agent 线程上下文、本地工具注册和嵌套 Pydantic 参数。
- 预算与约束、权限、审批恢复和有限重试。
- MySQL 8.0.12 Checkpoint 迁移兼容。
- 高德真实响应形状、跨城路线和条件注册。
- MCP 配置、Schema 适配、动态调用和真实 stdio 子进程生命周期。
- 飞书 Token 缓存、签名、去重、消息幂等和飞书审批。
- Auth、用户隔离、Memory、Task、Event、Outbox 和 Scheduler。
- Repository/Service 的查询、事务提交与回滚。
- 100 条评测数据的完整性和评分函数。

运行：

```powershell
cd backend
python -m ruff check app tests scripts
python -m pytest -q
node --check ..\frontend\app.js
```

Windows 受限沙箱可能禁止 stdio MCP 创建子进程；在普通 Conda 终端运行即可。

## 10. 真实 Agent 评测

`backend/evals/travel_cases.json` 有 100 条中文任务：

| 分类 | 数量 |
|---|---:|
| budget | 10 |
| itinerary_validation | 10 |
| weather | 12 |
| poi | 12 |
| route | 16 |
| preference | 10 |
| trip_read | 6 |
| trip_write | 10 |
| safety | 8 |
| composite | 6 |

评分脚本结合 HTTP 响应和 Harness 事件轨迹，计算：任务完成、响应成功、工具选择、约束、审批、P50/P95 延迟和分类通过率。

```powershell
cd backend
python scripts/evaluate.py --limit 10
python scripts/evaluate.py --category weather
python scripts/evaluate.py
```

输出 JSON 到终端，并写入 `backend/evals/latest_report.md`。报告是运行产物，不应把尚未执行的指标写进简历。

## 11. 功能完成标准

一个功能应同时具备：

- 真实业务入口。
- Pydantic 或等价输入边界。
- 明确权限等级。
- 有限失败策略。
- 至少一个自动化检查。
- 文档说明当前能力和边界。
