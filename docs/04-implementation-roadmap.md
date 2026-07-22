# 实现状态与演进记录

## 1. 文档用途

本项目的核心开发阶段已经完成。这份文档不再把已存在代码写成“未来计划”，而是说明每个阶段解决了什么问题、落在哪些文件、如何验证，以及当前仍有哪些边界。

## 2. 总体状态

| 阶段 | 状态 | 当前结果 |
|---|---|---|
| 0. 工程与 FastAPI | 完成 | Python 3.12、配置、健康检查、Swagger、静态页面 |
| 1. 最小单 Agent | 完成 | 千问、`create_agent`、预算工具、`/chat` |
| 2. 真实出行工具 | 完成 | 高德地理编码、POI、天气、三种路线、静态地图 |
| 3. 行程与约束 | 完成 | 领域模型、确定性校验、单事务保存、CRUD |
| 4. 权限与恢复 | 完成 | READ/WRITE/DANGEROUS、interrupt、MySQL Checkpoint |
| 5. Harness 能力 | 完成 | Memory、Task、Skill、摘要、有限重试、执行事件 |
| 6. MCP Host | 完成 | stdio、Streamable HTTP、动态工具发现、故障隔离 |
| 7. 飞书协作 | 代码完成 | Webhook、审批回复、文档/日历/消息；待真实环境验收 |
| 8. 自动任务 | 完成 | 24h/2h 天气复查、Agent 建议、Outbox、飞书通知 |
| 9. 产品与评测 | 完成 | 产品级前端、100 条评测、40 项自动化检查 |
| 部署/多 Agent | 明确排除 | 当前简历项目不做 Docker、CI/CD、云部署、多 Agent |

## 3. 阶段 0：工程与 FastAPI

### 已实现

- `backend/pyproject.toml` 管理运行和开发依赖。
- `backend/app/config.py` 使用 Pydantic Settings 读取根目录 `.env`。
- `backend/app/main.py` 创建 FastAPI、挂载路由和 `/ui` 静态页面。
- `/health`、`/version`、`/metrics`、`/integrations`。
- Ruff、pytest 配置和 `.gitignore` 密钥隔离。

### 验证

```powershell
cd backend
python -m uvicorn app.main:app --reload
python -m pytest tests/test_health.py -q
```

### 学习重点

应用组合根、lifespan、Router 汇总、Depends 依赖注入、Pydantic 请求/响应模型。

## 4. 阶段 1：最小单 Agent

### 已实现

- `agent/runtime.py` 使用 LangChain v1 `create_agent`。
- 默认接入千问 OpenAI 兼容接口。
- `budget.calculate_trip_cost` 使用 Decimal 做确定性计算。
- `/chat` 接收 `message`、`thread_id` 和 `channel`。
- Fake Model 自动化测试模型—工具循环。

### 验收用例

> 交通 200 元、住宿 500 元、餐饮 300 元、活动 0 元，预算 1000 元。

Agent 应选择预算工具并给出总计 1000、余额 0，而不是自己心算。

## 5. 阶段 2：真实出行数据

### 已实现

| 工具 | 文件 | 输出 |
|---|---|---|
| 地理编码 | `tools/amap.py` | 地址、坐标、行政区、来源、时间 |
| POI | `tools/amap.py` | 名称、地址、坐标、类型 |
| 路线 | `tools/amap.py` | 步行/驾车/公交时长、距离、步骤 |
| 天气 | `tools/weather.py` | 实况或预报、温度、风力、报告时间 |
| 静态地图 | `tools/amap.py` | 服务端代理 PNG，Key 不暴露给浏览器 |

外部响应被压缩为模型需要的字段；缺少高德 Key 时不注册 Agent 高德工具。

### 验证

`tests/test_amap_tools.py` 使用 Mock HTTP 响应验证高德真实返回结构，无需测试时访问网络。

## 6. 阶段 3：领域约束与持久化

### 已实现

- `TripRequirement`、`Itinerary`、`ItineraryItem` Pydantic 领域模型。
- `validate_itinerary` 检查时间范围、时间重叠、预算、步行限制、必去地点。
- `trip.save_itinerary` 先校验，再用一个 MySQL 事务保存行程和全部日程。
- Controller → Service → Repository → ORM 分层。
- Web API 支持行程和日程完整 CRUD、归档及地图。

### 未实现的约束

营业时间、景点关闭、路线交通缓冲尚未进入确定性引擎，不应在演示中声称已经支持。

## 7. 阶段 4：权限、审批与 Checkpoint

### 已实现

- 每个工具声明 `RiskLevel`。
- READ 自动执行，WRITE 进入 `interrupt()`，DANGEROUS 拒绝。
- `GET /approvals/{thread_id}` 查询待审批工具。
- `POST /approvals/{thread_id}` 批准或拒绝并恢复。
- LangGraph MySQL Checkpoint 支持跨请求、跨重启恢复。
- 自定义 Checkpointer 兼容 MySQL 8.0.12 的 JSON 限制。

### 验证

`tests/test_harness.py` 覆盖写工具中断和恢复、权限决策、重试和 Checkpoint 迁移。

## 8. 阶段 5：Harness 能力

### Memory

用户明确偏好进入 MySQL，动态 Prompt 每轮读取；写入本身需要审批。

### Task

支持创建、列出和完成带 `blocked_by` 的持久任务。当前单 Agent 执行全部任务。

### Skill

启动只加载 `name/description`，需要时调用 `skill.load` 读取完整内容。当前有预算旅行和家庭旅行两个 Skill。

### Context

LangChain `SummarizationMiddleware` 在长会话中生成摘要；另有确定性消息裁剪辅助函数。

### Recovery 与事件

READ 工具的超时/连接错误最多重试两次；EventBroker 为前端和评测记录 run/tool/approval 事件。

## 9. 阶段 6：MCP Host

### 已实现

- Pydantic 验证 `mcp.json`。
- stdio 和 Streamable HTTP Client。
- 每个 Server 独立 Session 与清理栈。
- `initialize`、`list_tools`、`call_tool`。
- JSON Schema 转 Pydantic 参数模型。
- 动态命名空间和 Harness 风险识别。
- 单 Server 失败隔离。
- Fake stdio MCP 的真实子进程生命周期测试。

### 当前边界

没有运行中自动热重连；MCP Server 在应用启动时建立连接。

## 10. 阶段 7：飞书协作

### 代码已完成

- 入站 Webhook 验证、文本解析、用户/群聊映射和 MySQL 去重。
- 飞书中用“批准/拒绝”恢复 Agent。
- 官方远程 MCP tenant token 缓存与允许工具白名单。
- 官方 `lark-mcp` 消息、docx 文档和日历工具。
- 普通回复和天气通知使用幂等 Outbox。

### 仍需人工验收

1. 飞书开放平台为应用增加消息、文档和日历权限。
2. 发布应用版本并配置事件订阅。
3. 提供公网 HTTPS `/webhooks/feishu`。
4. 从飞书完成一次“提问 → 审批 → 写文档/日历 → 回复”。

这属于外部环境配置，不需要继续增加项目模块。

## 11. 阶段 8：自动任务

### 已实现

- 行程创建/开始时间变化时维护 24h、2h 天气任务。
- Scheduler 每分钟扫描到期任务。
- 高德天气失败最多尝试三次。
- 同一 Agent 根据真实天气生成调整建议。
- 结果存入 `scheduled_jobs.result`。
- 飞书来源行程主动发送建议，消息失败进入 Outbox。
- `GET /automations` 查看任务，`POST /automations/run` 手动触发到期扫描。

当前只生成建议，不自动修改行程。

## 12. 阶段 9：产品与评测

### Web 产品

- 仪表盘与能力状态。
- 登录/注册。
- Agent 聊天、历史恢复、SSE 运行进度、审批卡片。
- 行程搜索、状态筛选、创建、编辑、归档、删除。
- 日程项管理和高德静态地图。
- 响应式布局和基本无障碍标签。

### 评测

100 条用例分类：

```text
预算 10            约束 10          天气 12
POI 12             路线 16          偏好 10
行程读取 6         行程写入 10      安全 8
复合任务 6
```

评测脚本读取 `/chat/{thread_id}/events/snapshot`，因此能够检查实际工具轨迹，不再只判断回复非空。

## 13. 当前 Definition of Done

本地代码完成标准：

- Ruff 通过。
- `node --check frontend/app.js` 通过。
- pytest 当前 40 项通过。
- `.env`、`config/mcp.json` 没有进入 Git。
- README、API、数据表和功能边界与代码一致。

简历展示前还需：

- 跑一次真实 100 条评测并保存报告。
- 录制或截图一次飞书真实闭环。
- 只引用真实评测数字，不写未经验证的成功率。
