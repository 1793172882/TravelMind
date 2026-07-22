# 项目驱动学习路线

## 1. 学习方法

项目已经完成，学习时不要重新从零搭架构。按照真实请求链路阅读、运行、修改一个小实验、再恢复代码：

```text
提出一个业务问题
→ 找到入口 API
→ 跟踪 Service/Agent/Harness
→ 找到数据库或外部工具
→ 运行对应测试
→ 用自己的话画出流程
```

每个主题回答四个问题：

1. 它解决什么真实问题？
2. 数据和控制权由谁持有？
3. 框架完成了什么，TravelMind 自己完成了什么？
4. 失败、重启或拒绝审批后会怎样？

## 2. 第一阶段：FastAPI 与分层

### 阅读顺序

```text
backend/app/main.py
→ backend/app/api/router.py
→ backend/app/api/routes/trips.py
→ backend/app/api/dependencies.py
→ backend/app/services/trip.py
→ backend/app/infrastructure/repositories/trip.py
→ backend/app/infrastructure/models/trip.py
```

### 必须掌握

- FastAPI app、Router、Depends、Pydantic Schema。
- Controller 只处理 HTTP，Service 管业务和事务，Repository 写 ORM 查询。
- 请求级 SQLAlchemy Session 如何创建和关闭。
- 为什么 Controller 不应直接调用 MySQL。

### 实验

1. 在 Swagger 调用 `POST /trips`。
2. 给 `origin` 传空字符串，观察 Pydantic 的 422。
3. 使用同一个用户查询行程，再换用户 Token 验证隔离。
4. 阅读 `tests/test_trip_service.py`，解释 commit/rollback 属于哪一层。

### 完成标准

能够画出 `POST /trips` 从 HTTP 到 MySQL 的完整调用链。

## 3. 第二阶段：LLM、Agent 与 Tool Calling

### 阅读顺序

```text
agent/prompts.py
→ tools/budget.py
→ harness/tool_registry.py
→ agent/runtime.py::_langchain_tools
→ agent/runtime.py::build_agent_runtime
→ api/routes/chat.py
```

### 必须掌握

- LLM、Agent、Harness 的区别。
- LangChain `create_agent` 如何完成模型—工具循环。
- `StructuredTool`、Pydantic 参数和 Tool Result。
- `AgentContext` 与聊天消息的区别。
- 为什么数学、时间和距离不能依赖模型猜测。

### 实验

- 运行预算问题，查看 SSE 中的 `tool.started/tool.completed`。
- 临时把预算工具描述改模糊，观察 100 条评测中的工具选择变化。
- 阅读 `tests/test_agent_runtime.py` 的 Fake Model 调用链。

### 完成标准

能够解释为什么项目没有手写 `while model_calls_tool` 循环。

## 4. 第三阶段：LangGraph 持久化与审批

### 阅读顺序

```text
harness/permissions.py
→ harness/middleware.py
→ infrastructure/checkpoint.py
→ agent/runtime.py::chat/resume
→ api/routes/approvals.py
```

### 必须掌握

- Checkpoint、业务数据库和 Memory 的区别。
- `thread_id` 为什么是恢复键。
- `interrupt()` 如何暂停在工具调用位置。
- `Command(resume=True/False)` 如何继续。
- 为什么“模型选择工具”不等于“系统允许执行”。

### 实验

1. 明确要求保存偏好或行程。
2. 查看 `/approvals/{thread_id}`。
3. 重启服务后使用相同线程批准。
4. 再做一次拒绝，确认原写操作没有执行。

### 完成标准

能够分别解释聊天历史、执行现场、业务行程和长期偏好存在哪里。

## 5. 第四阶段：确定性约束

### 阅读顺序

```text
domain/models.py
→ domain/constraints.py
→ tools/itinerary.py
→ tools/trips.py::save_itinerary_record
→ services/trip.py::create_trip_with_items
```

### 必须掌握

- Pydantic 领域模型和 ORM 模型为什么分开。
- 时间重叠、预算和步行距离为什么使用普通 Python。
- 校验和保存为什么必须处在同一业务流程。
- 单事务保存行程和日程如何避免部分数据。

### 实验

- 构造两个重叠日程。
- 构造预算和步行同时超限的日程。
- 构造缺少必去地点的日程。
- 运行 `tests/test_harness.py::test_budget_and_constraint_validation`。

### 当前边界

不要把营业时间、景点关闭和交通缓冲当成已实现规则。可以把其中一项作为后续练习，但不是简历项目必需功能。

## 6. 第五阶段：真实外部工具

### 阅读顺序

```text
tools/amap.py
→ tools/weather.py
→ agent/runtime.py::build_default_registry
→ tests/test_amap_tools.py
```

### 必须掌握

- 异步 HTTP、超时和异常归一化。
- 外部大 JSON 为什么要压缩成模型需要的字段。
- 数据来源 `source` 和查询时间 `observed_at`。
- 地理编码如何支持路线工具直接接收中文地点。
- Key 为什么只能留在服务端。

### 实验

- 分别查询 POI、天气和三种路线。
- 注入超时，观察 READ 工具有限重试。
- 删除本地高德 Key，观察工具不再注册且 Agent 明确降级。

## 7. 第六阶段：Memory、Task、Skill 与上下文

### Memory

阅读 `harness/memory.py` 和动态 Prompt。观察用户明确说“请记住我是素食者”时为何先审批、再合并 MySQL 记录。

### Task

阅读 `harness/tasks.py`，手动创建 A 和依赖 A 的 B；只有 A 完成后 B 才进入 runnable。

### Skill

阅读 `harness/skills.py` 和两个 `SKILL.md`。比较启动时目录摘要与 `skill.load` 返回的完整内容。

### Context

阅读 `SummarizationMiddleware` 配置和 `harness/context.py`，区分模型摘要与确定性裁剪。

### 完成标准

能够解释短期上下文、长期偏好、任务状态和按需知识为什么需要四种不同机制。

## 8. 第七阶段：MCP

### 阅读顺序

```text
config/mcp.example.json
→ mcp/config.py
→ mcp/manager.py
→ mcp/tool_adapter.py
→ agent/runtime.py::register_mcp_tools
→ tests/test_mcp.py
```

### 必须掌握

- Host、Client、Server 的角色。
- stdio 与 Streamable HTTP 的差异。
- `initialize`、`tools/list`、`tools/call`。
- 为什么每个 Server 有独立 Session。
- MCP 工具为什么仍要进入 Harness 权限管线。

### 实验

```powershell
cd backend
python scripts/check_mcp.py
python -m pytest tests/test_mcp.py -q
```

再启用 Fake MCP，观察工具名称由 Server 命名空间限定。

## 9. 第八阶段：飞书 Channel 与 MCP

### 阅读顺序

```text
channels/feishu.py
→ api/routes/webhooks.py
→ mcp/feishu_auth.py
→ infrastructure/outbox.py
→ main.py 中的天气通知
```

### 必须掌握

- Channel 解决“消息怎么进入”，MCP 解决“Agent 怎么操作外部系统”。
- Webhook 签名、快速响应和事件幂等。
- 普通回复为什么不让模型主动选择消息工具。
- Outbox 为什么比请求内无限重试可靠。

### 实验

- 用测试 Payload 验证 challenge、错误 Token 和重复事件。
- 运行飞书 Token 缓存测试。
- 在真实飞书环境完成一次审批回复。

## 10. 第九阶段：Scheduler 与主动 Agent

### 阅读顺序

```text
harness/scheduler.py
→ services/trip.py 中的 schedule/cancel
→ main.py::replan
→ api/routes/automations.py
```

### 必须掌握

- 请求内 Background Task 和持久 Scheduler 的区别。
- Job 如何在 MySQL 中跨重启保留。
- 失败次数、结果和最后错误如何记录。
- 为什么天气变化只生成建议，不自动篡改行程。

### 实验

- 创建开始时间接近当前时间的行程。
- 调整 Job 的 `run_at` 后调用 `POST /automations/run`。
- 查看 `scheduled_jobs.result` 和飞书通知。

## 11. 第十阶段：评测

### 阅读顺序

```text
backend/evals/travel_cases.json
→ backend/scripts/evaluate.py
→ api/routes/chat.py::chat_event_snapshot
→ tests/test_evaluation.py
```

评测不是比较固定文本，而是观察：

- API 是否成功并返回消息。
- 是否选择了预期工具。
- 是否调用了禁止写工具。
- 回答是否包含必要约束词。
- 是否正确进入或避免审批。
- 延迟和分类通过率。

开发时先运行：

```powershell
python scripts/evaluate.py --limit 10
```

确认成本和外部服务稳定后再运行全部 100 条。报告中的真实数字才可以写进简历。

## 12. 面试表达模板

每个亮点都按“问题—设计—实现—验证—边界”表达。例如：

```text
问题：模型可能在用户未确认时执行外部写入。
设计：所有本地和 MCP 工具统一经过风险分级。
实现：WRITE 工具触发 LangGraph interrupt，并用 MySQL Checkpoint 保存执行位置。
验证：自动化测试覆盖批准和拒绝；真实评测检查审批状态。
边界：目前没有细粒度角色权限，适合本地个人项目。
```

不要只背“使用 LangChain、LangGraph、MCP”，要能从具体文件讲出控制流、数据流、失败路径和取舍。
