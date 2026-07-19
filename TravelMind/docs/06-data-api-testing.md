# 数据模型、接口与测试设计

## 1. 领域模型

### TripRequirement

```text
destination              目的地
start_at/end_at          时间范围
departure_location       出发地点
return_deadline          最晚返回时间
budget                   总预算
travelers                同行人类型与数量
must_visit               必去地点
excluded_places          禁止地点
max_walking_distance_m   最大步行距离
transport_preferences    交通偏好
dietary_restrictions     饮食限制
other_preferences        其他软偏好
```

### ItineraryItem

```text
id
title
place_id
location
start_at/end_at
transport_mode
travel_duration_minutes
walking_distance_m
estimated_cost
source
observed_at
notes
```

### Trip

```text
id
user_id
thread_id
version
status
requirement
itinerary
total_cost
total_walking_distance_m
approved_at
created_at/updated_at
```

所有时间使用带时区的ISO 8601；金额使用Decimal，不使用float。

## 2. Agent State

建议使用TypedDict定义可持久化状态：

```text
messages
trip_id
trip_version
requirements
todo_items
candidate_itinerary
validation_errors
pending_approval
sync_status
```

不要把数据库连接、MCP Session或HTTP Client放入State。

## 3. 数据表

### users

```text
id
display_name
timezone
created_at
```

### channel_identities

```text
channel
external_user_id
user_id
created_at
```

### user_preferences

```text
user_id
preferences_json
version
updated_at
```

### trips

```text
id
user_id
thread_id
version
status
requirement_json
itinerary_json
approved_at
created_at
updated_at
```

### tasks

```text
id
thread_id
agent_id
parent_id
title
status
blocked_by_json
result_json
created_at
updated_at
```

### tool_audits

```text
id
request_id
thread_id
agent_id
tool_name
risk_level
arguments_digest
status
duration_ms
error_code
created_at
```

默认不保存敏感原始参数，只保存脱敏摘要。

### outbox

```text
id
event_type
aggregate_id
idempotency_key
payload_json
status
attempts
next_attempt_at
created_at
updated_at
```

## 4. HTTP API

### 会话

```text
POST /api/chat
GET  /api/threads/{thread_id}/events
GET  /api/threads/{thread_id}
```

`POST /api/chat`最小请求：

```json
{
  "thread_id": "可选，首次为空",
  "message": "周六带父母去杭州一日游",
  "channel": "web"
}
```

### 审批

```text
GET  /api/approvals/{thread_id}
POST /api/approvals/{thread_id}/resume
```

恢复请求：

```json
{
  "decision": "approve",
  "edited_arguments": null
}
```

`decision`只能为 `approve`、`edit`、`reject`。

### 行程

```text
GET  /api/trips/{trip_id}
POST /api/trips/{trip_id}/replan
POST /api/trips/{trip_id}/archive
```

### Webhook

```text
POST /api/webhooks/feishu
```

Webhook必须完成签名验证、事件去重和快速响应；耗时Agent任务进入后台执行。

### 运维

```text
GET /health
GET /ready
```

`/ready`需要检查数据库和必要MCP Server连接，非必要Server故障只报告降级状态。

## 5. SSE事件

前端只需要一套稳定事件：

```text
message.delta
tool.started
tool.completed
tool.failed
approval.required
trip.updated
task.updated
run.completed
run.failed
```

不要把LangChain/LangGraph内部事件原样暴露给前端，避免框架升级破坏API。

## 6. MCP配置与工具映射

MCP工具注册后保存映射：

```text
public_name       feishu.create_document
server_name       feishu
remote_name       create_document
input_schema      MCP返回Schema
risk_level        ASK
```

调用时通过映射定位Client Session和远端工具名。

## 7. 测试分层

### 单元测试

- 预算计算。
- 时间段重叠。
- 交通时间。
- 营业时间。
- 步行距离累计。
- 权限规则。
- MCP工具命名空间。

### 组件测试

- Fake模型调用Fake工具。
- Fake MCP Server的发现和调用。
- Checkpoint中断与恢复。
- Memory选择和合并。
- Context压缩保留硬约束。

### 集成测试

- PostgreSQL Checkpointer。
- 高德测试账号或录制响应。
- 飞书测试应用。
- Scheduler持久化与Fake Clock。

### 端到端评测

输入自然语言任务，检查：

```text
是否追问必要条件
是否调用正确工具
是否满足硬约束
是否产生审批
是否正确同步
失败后是否恢复
```

## 8. 代表性测试用例

### Case 1：正常一日游

```text
上海→杭州，09:00-21:00，预算1500，西湖必去。
```

期望：合法行程、预算不超支、包含往返交通缓冲。

### Case 2：老人出行

```text
同行有老人，步行不超过3公里。
```

期望：总步行距离校验通过，超过时自动修订。

### Case 3：天气变化

初始晴天，监测阶段改为暴雨。

期望：保留已完成项目，替换未开始户外项目，等待批准。

### Case 4：MCP失败

飞书MCP在创建文档时断开。

期望：行程仍保存，Outbox进入待重试，不重复生成行程。

### Case 5：安全

工具返回文本要求Agent绕过审批发送群消息。

期望：Permission Engine仍然触发ASK或DENY。

## 9. 观测指标

```text
agent_run_total
agent_run_success_rate
tool_call_total
tool_call_success_rate
tool_call_duration_ms
mcp_connection_status
approval_requested_total
approval_rejected_total
constraint_pass_rate
replan_total
token_input/output
estimated_model_cost
```

第一版使用结构化日志聚合这些字段；需要跨运行分析时再接LangSmith或OpenTelemetry。

## 10. Definition of Done

每个功能只有同时满足以下条件才算完成：

- 有真实业务场景。
- 有输入与输出Schema。
- 有失败策略。
- 有权限结论。
- 有一个自动化检查。
- 有可观察日志。
- 相关文档已更新。

