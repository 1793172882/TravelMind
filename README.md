# TravelMind

TravelMind 是一个基于 Harness 思想构建的单 Agent 智慧出行助手。项目使用 LangChain/LangGraph 组织模型、工具调用、Checkpoint 与人工审批；使用自研 Harness 统一管理工具注册、权限、恢复、记忆、任务、Skill 和 MCP Client；通过 FastAPI 同时服务 Web 页面和飞书消息入口。

```text
Web / 飞书
    ↓
FastAPI API / Channel
    ↓
LangChain create_agent + LangGraph Checkpoint
    ↓
Harness（Registry → Permission → Interrupt → Retry）
    ├── 本地工具：预算、约束、行程、Memory、Task、Skill
    ├── 高德 Web 服务：地理编码、POI、天气、路线、静态地图
    └── MCP Manager：飞书远程 MCP、官方 lark-mcp、其他 MCP Server

HTTP 行程接口：Controller → Service → Repository → SQLAlchemy → MySQL
```

## 已实现能力

| 模块 | 当前实现 |
|---|---|
| Agent | 千问 `qwen3.5-plus`、LangChain `create_agent`、多轮对话、动态 Prompt、长上下文摘要 |
| LangGraph | MySQL Checkpoint、按 `thread_id` 恢复、`interrupt` 审批与继续执行 |
| Harness | Tool Registry、Pydantic 参数校验、READ/WRITE/DANGEROUS 权限、有限重试、执行事件 |
| 出行工具 | 预算计算、行程约束校验、高德地理编码、POI、天气、步行/驾车/公交路线 |
| 数据 | MySQL 行程和日程 CRUD、完整行程单事务保存、用户/会话隔离 |
| 记忆与任务 | MySQL 用户偏好、带依赖 Task、按需加载本地 Skill |
| MCP | stdio 与 Streamable HTTP、动态工具发现、独立 Session、单 Server 故障隔离 |
| 飞书 | Webhook 验证/去重、消息回复、审批回复、文档/日历/消息工具、Outbox 重试 |
| 自动化 | 出发前 24/2 小时天气复查、Agent 调整建议、飞书主动通知 |
| Web 产品 | 登录注册、Agent 对话、SSE 进度、审批、聊天历史、行程管理、静态地图 |
| 评测 | 100 条中文用例，统计任务完成率、工具选择、约束、审批与 P50/P95 延迟 |

当前自动化检查为 **40 passed**。项目定位是本地可运行、可演示、可用于简历讲解的产品级 MVP，不包含云端部署和多 Agent。

## 项目结构

```text
TravelMind/
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI Controller、Schema、依赖组合
│   │   ├── services/            # 业务流程与事务边界
│   │   ├── domain/              # 纯业务模型与确定性约束
│   │   ├── infrastructure/      # SQLAlchemy、Repository、Checkpoint、Outbox
│   │   ├── agent/               # 单 Agent、Prompt、运行上下文
│   │   ├── harness/             # 工具、权限、恢复、记忆、任务、Skill、Scheduler
│   │   ├── mcp/                 # MCP Client Manager、认证与工具适配
│   │   ├── channels/            # 飞书入站渠道
│   │   ├── tools/               # 本地业务工具和高德工具
│   │   └── main.py              # 应用组合根与 lifespan
│   ├── evals/                   # 100 条 Agent 评测数据
│   ├── scripts/                 # MCP 检查、真实 Agent 评测
│   ├── tests/                   # 40 项自动化检查
│   ├── schema.sql
│   └── pyproject.toml
├── frontend/                    # 无 Node 依赖的原生 Web 页面
├── config/                      # MCP 配置模板
├── skills/                      # 按需加载的领域 Skill
├── docs/                        # 产品、架构、实现和学习文档
├── .env.example
└── README.md
```

完整文件职责见 [项目结构与模块职责](docs/07-project-structure.md)。

## 快速开始

### 1. 安装

```powershell
conda create -n travelmind python=3.12 -y
conda activate travelmind
cd TravelMind\backend
python -m pip install -e ".[dev]"
```

### 2. 配置 MySQL

MySQL 8.x 执行 [backend/schema.sql](backend/schema.sql)，然后在仓库根目录创建本地配置：

```powershell
Copy-Item .env.example .env
```

至少填写：

```dotenv
DATABASE_URL=mysql+pymysql://用户名:密码@127.0.0.1:3306/travelmind?charset=utf8mb4
DASHSCOPE_API_KEY=阿里云百炼APIKey
AMAP_API_KEY=高德Web服务Key
AUTH_SECRET=本地长随机字符串
```

应用启动时会创建缺少的业务表；LangGraph 会单独初始化 Checkpoint 表。当前兼容 MySQL 8.0.12。

### 3. 启用 MCP（可选）

```powershell
Copy-Item config\mcp.example.json config\mcp.json
```

在 `config/mcp.json` 中只启用已配置的 Server。密钥仅写入 `.env`；`.env` 与 `config/mcp.json` 均被 Git 忽略。

| 集成 | 关键配置 | 用途 |
|---|---|---|
| 千问 | `DASHSCOPE_API_KEY` | 对话与工具调用 |
| 高德 | `AMAP_API_KEY` | 地点、POI、天气、路线、地图 |
| 飞书入站 | `FEISHU_VERIFICATION_TOKEN`、`FEISHU_ENCRYPT_KEY` | Webhook 校验 |
| 飞书官方 MCP | `FEISHU_APP_ID`、`FEISHU_APP_SECRET` | tenant token 与远程文档工具 |
| 官方 lark-mcp | 同上，并启用 `lark_openapi` | 消息、文档、日历写入 |

检查 MCP 连接（不会输出凭证）：

```powershell
cd backend
python scripts/check_mcp.py
```

### 4. 启动

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Swagger：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 产品界面：[http://127.0.0.1:8000/ui/](http://127.0.0.1:8000/ui/)

## 主要 API

```text
POST /auth/register              POST /auth/login             GET /auth/me
POST /chat                       GET  /chat/{thread_id}/history
GET  /chat/{thread_id}/events    GET  /chat/{thread_id}/events/snapshot
GET  /approvals/{thread_id}      POST /approvals/{thread_id}

POST /trips/preview              POST /trips                   GET /trips
GET/PATCH/DELETE /trips/{trip_id}
POST /trips/{trip_id}/archive
POST/GET /trips/{trip_id}/items
PATCH/DELETE /trips/{trip_id}/items/{item_id}
GET /trips/{trip_id}/map

GET /automations                 POST /automations/run
POST /webhooks/feishu
GET /health                      GET /version
GET /metrics                     GET /integrations
```

接口不使用额外 `/api` 前缀。`AUTH_REQUIRED=false` 时允许匿名学习；开启后需携带登录返回的 Bearer Token。

## 测试与 Agent 评测

```powershell
cd backend
python -m ruff check app tests scripts
python -m pytest -q
node --check ..\frontend\app.js
```

服务启动后运行真实模型/工具评测：

```powershell
python scripts/evaluate.py --limit 10
python scripts/evaluate.py --category route
python scripts/evaluate.py
```

完整运行会在 `backend/evals/latest_report.md` 生成报告。100 条用例分为预算、约束、天气、POI、路线、偏好、行程读写、安全和复合任务。真实评测会消耗模型额度并调用高德服务。

## 当前边界

- 飞书代码链路已完成，但真实端到端验收依赖应用权限、版本发布、事件订阅和公网 HTTPS Webhook。
- 静态地图展示地点标记，不提供交互式道路折线。
- `/metrics` 与 SSE 事件保存在单进程内存中，重启后清空。
- 项目没有 Alembic 版本化迁移、Docker Compose、CI/CD、云部署和多 Agent。
- 不做自动付款、抢票、下单、非官方微信登录或无数据依据的实时价格承诺。

## 文档

1. [产品需求与当前范围](docs/01-product-requirements.md)
2. [详细架构设计](docs/02-architecture-design.md)
3. [Harness 与 MCP 设计](docs/03-harness-and-mcp-design.md)
4. [实现状态与演进记录](docs/04-implementation-roadmap.md)
5. [项目驱动学习路线](docs/05-project-learning-guide.md)
6. [数据模型、API 与测试](docs/06-data-api-testing.md)
7. [项目结构与模块职责](docs/07-project-structure.md)
