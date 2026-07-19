# 实现流程与里程碑

## 1. 实施原则

- 每个阶段必须留下一个可运行、可演示的结果。
- 一次只新增一个Harness机制，观察它解决的问题。
- 先用假数据验证Agent流程，再接真实外部API。
- 每个非平凡阶段至少有一个自动化测试。
- 未完成当前阶段验收前，不进入下一阶段。

## 2. 阶段总览

| 阶段 | 交付结果 | 主要学习主题 |
|---|---|---|
| 0 | 工程可运行 | Python工程、配置、测试 |
| 1 | 最小Agent对话 | LLM、Messages、Tool Calling |
| 2 | 真实出行工具 | Tool Schema、异步HTTP、结构化结果 |
| 3 | 可执行行程 | Structured Output、确定性校验 |
| 4 | 权限与恢复 | Middleware、Interrupt、Checkpoint |
| 5 | 完整Harness | Todo、Skill、Compact、Memory、Recovery |
| 6 | MCP Host | MCP Client、Tool Discovery、连接生命周期 |
| 7 | 飞书协作 | Webhook、文档、表格、日历、审批 |
| 8 | 长运行任务 | Background、Cron、Outbox、重规划 |
| 9 | 产品化 | 前端、评测、观测、部署、简历材料 |

## 3. 阶段0：工程骨架

### 目标

建立最小Python后端，不创建尚未使用的模块。

### 实现

- 创建 `backend/pyproject.toml`。
- 创建FastAPI健康检查 `/health`。
- 使用Pydantic Settings读取环境变量。
- 配置Ruff和pytest。
- 增加 `.env.example`，不提交真实密钥。

### 验收

```text
服务可启动
GET /health 返回200
pytest可运行
ruff check通过
```

### 学习问题

- 为什么密钥不能进入Prompt和日志？
- 什么是应用lifespan？

## 4. 阶段1：最小单Agent

### 目标

理解Agent最小循环，而不是先做完整产品。

### 实现

- 使用LangChain v1 `create_agent`。
- 接入一个可配置模型。
- 添加一个纯函数工具 `calculate_trip_cost`。
- 提供 `/chat` 接口。
- 打印或记录模型消息、Tool Call和Tool Result。

### 验收场景

用户问：

> 交通200元，酒店500元，餐饮300元，总预算1000元，是否超支？

Agent必须调用计算工具，并回答未超支，剩余0元。

### 自动化检查

- 工具金额计算测试。
- 模型可用Fake Chat Model替代，测试工具调用流程。

### 学习问题

- LLM和Agent有什么区别？
- Tool描述为什么会影响工具选择？
- Tool Result为什么必须回到消息序列？

## 5. 阶段2：地点、天气和路线工具

### 目标

让Agent通过Harness观察真实世界。

### 实现顺序

1. Fake天气工具。
2. Fake地点搜索工具。
3. Fake路线工具。
4. 将Fake实现替换为高德等官方接口。
5. 将外部响应转换为内部Pydantic模型。

### 工具约束

- 输入和输出都有Schema。
- 网络请求有超时。
- 不返回无关原始字段。
- 返回来源、查询时间和错误类型。
- 同类独立查询可以并行。

### 验收

Agent能够查询两个地点和路线，输出数据来自工具而非模型臆测。

### 学习问题

- 工具应当多大粒度？
- 哪些错误应重试，哪些应交回模型？

## 6. 阶段3：结构化行程与约束引擎

### 目标

区分LLM推理和确定性业务规则。

### 实现

- 定义 `TripRequirement`、`Itinerary`、`ItineraryItem`。
- 使用LangChain结构化输出生成候选行程。
- 实现普通Python约束校验：
  - 时间重叠。
  - 路线时间是否足够。
  - 总预算。
  - 总步行距离。
  - 营业时间。
- 校验失败时将明确错误返回Agent修订。

### 验收

给出故意冲突的候选行程，约束引擎必须稳定发现问题；不调用LLM也能完成校验。

### 自动化检查

建立一张参数化测试表，覆盖：

- 正常行程。
- 时间重叠。
- 预算超支。
- 步行超限。
- 地点关闭。

### 学习问题

- 为什么数学和时间规则不应交给模型？
- Structured Output失败时如何恢复？

## 7. 阶段4：权限、审批和Checkpoint

### 目标

让Agent可以安全中断并恢复。

### 实现

- 为工具标记 `ALLOW/ASK/DENY`。
- 使用LangChain Middleware包裹工具调用。
- 使用LangGraph Checkpointer保存线程状态。
- 对模拟的 `calendar.create_event` 使用 `interrupt()`。
- 提供批准、修改、拒绝接口。
- 重启进程后用相同 `thread_id` 恢复。

### 验收

```text
Agent请求创建日历
→ 系统暂停
→ 数据库存在Checkpoint
→ 重启服务
→ 用户批准
→ 从原位置继续
```

### 学习问题

- Checkpoint与业务数据库有什么区别？
- 为什么“模型想调用”不等于“系统允许调用”？

## 8. 阶段5：完整Harness

### 目标

参考 `learn-claude-code`，逐个加入单Agent需要的Harness机制。

### 5.1 Todo与Task

- Agent维护当前Todo。
- 长任务保存到Task表。
- Task支持 `blocked_by`。
- 当前仍由同一个Agent执行全部任务。

### 5.2 Skill Loading

- Skill目录保存家庭出行、预算旅行等知识。
- 启动时只加载Skill清单。
- 模型需要时再加载完整内容。

### 5.3 Context Compact

- 先裁剪工具结果。
- 再生成结构化摘要。
- 记录压缩前后Token变化。

### 5.4 Memory

- 从对话提取明确用户偏好。
- 让用户确认敏感或重要偏好。
- 新会话按需注入相关记忆。

### 5.5 Error Recovery

- 模拟超时、限流、格式错误和上下文过长。
- 验证重试次数有上限。
- 记录最终采取的恢复策略。

### 验收

运行一个至少经过5轮工具调用的任务，确认任务、记忆、压缩、错误恢复和审计都能观察到。

## 9. 阶段6：内置MCP Client

### 目标

让Harness无需修改Agent Loop即可接入外部能力。

### 实现

1. 编写最小测试MCP Server，暴露 `echo` 和 `get_weather`。
2. 使用官方MCP Python SDK建立stdio连接。
3. 执行 `initialize` 和 `list_tools`。
4. 将MCP Tool转换并注册到Tool Registry。
5. 通过Agent调用 `call_tool`。
6. 增加Streamable HTTP连接。
7. 增加每个Server独立的重连和清理。

### 验收

- 修改 `mcp.json` 即可启用或停用Server。
- 增加MCP工具不修改Agent Runtime。
- 一个Server断开不影响本地工具。
- MCP工具仍受Permission Engine控制。

### 学习问题

- MCP Host、Client和Server分别是什么？
- 为什么每个Server需要独立Session？
- MCP Tool与普通LangChain Tool如何统一？

## 10. 阶段7：飞书协作

### 实现顺序

1. 接收并验证飞书Webhook。
2. 将飞书用户映射到系统用户。
3. 通过飞书MCP创建行程文档草稿。
4. 写入多维表格。
5. 经审批后创建日历事件。
6. 写操作增加幂等键和Outbox。

### 验收

从飞书发起需求，系统完成规划、审批、文档创建和日历写入；重复回调不会创建重复内容。

## 11. 阶段8：后台任务与定时重规划

### 实现

- APScheduler使用PostgreSQL持久化Job。
- 行程前24小时和2小时检查天气。
- 发现明显变化后创建重规划Task。
- 生成替代方案后等待用户审批。
- 失败通知进入Outbox并重试。

### 验收

通过Fake Clock模拟时间推进，不需要真正等待24小时；任务触发、重规划和通知完整可测。

## 12. 阶段9：产品化与简历交付

### 产品交付

- React聊天界面。
- 行程时间轴和地图标记。
- SSE展示模型、工具和审批事件。
- Docker Compose一键启动。

### 工程交付

- 20个左右代表性评测任务。
- 架构图、演示视频和部署说明。
- 关键指标：成功率、约束满足率、工具成功率、成本、延迟。

### 简历交付

形成：

- 一段项目描述。
- 3到5条量化技术亮点。
- 一份5分钟项目讲解。
- 一套架构与故障处理面试题。

## 13. 每阶段提交格式

建议每阶段使用一个小提交：

```text
feat(agent): add minimal tool-calling loop
feat(tools): add structured route search
feat(harness): add permission middleware
feat(mcp): discover and register server tools
```

每个提交同时更新：

- 对应文档。
- 一个可执行演示。
- 最小自动化测试。

