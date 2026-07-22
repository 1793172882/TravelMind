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
    ├── 高德 Web 服务 → 地点/POI/天气/路线
    └── MCP Client Manager → 飞书/其他 MCP Server

Controller → Service → Repository → SQLAlchemy ORM → MySQL
```

## 当前已实现

- MySQL 行程与日程项 CRUD，严格遵循 Controller → Service → Repository 分层。
- LangChain `create_agent` 单 Agent 与可跨重启恢复的 MySQL LangGraph Checkpoint。
- 阿里云百炼千问 `qwen3.5-plus` 默认模型（OpenAI 兼容协议）。
- 高德真实地理编码、POI、天气、步行/驾车/公交路线工具。
- 基于 `thread_id` 的多轮对话、工具调用、人工审批、暂停与恢复。
- Harness Tool Registry、Pydantic 参数校验、权限分级、失败重试。
- 上下文压缩、用户偏好 Memory、依赖任务、Skill 按需加载的最小实现。
- Memory 与 Task 已持久化到 MySQL，并通过动态 Prompt/工具真正接入 Agent。
- 内置 MCP Manager，支持 stdio 和 Streamable HTTP；每个 Server 独立 Session 和故障隔离。
- MCP 工具动态发现并进入统一 Harness 权限管线。
- 飞书 Webhook challenge、token/签名校验、文本消息转换和事件去重。
- 约束复验后一次审批、单事务保存完整行程与全部日程项。
- 本地账号登录与用户级行程、Checkpoint 会话隔离。
- MySQL Outbox、持久 Webhook 去重、出发前 24/2 小时天气复查与自动重规划。
- 无 Node 依赖的响应式页面，包含 SSE 工具进度、服务端聊天历史、静态地图及完整行程编辑。
- 20 条 Agent 评测集与 38 个自动化测试（包含真实 stdio MCP 生命周期）。

当前是“可运行的后端 MVP”，不是所有外部服务都开箱即用。真实模型调用需要阿里云百炼 Key，高德实时数据需要 Web 服务 Key；飞书写文档、日历等能力需要可用的飞书 MCP Server。项目不会提交任何真实密钥。

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

首次启动会自动创建 LangGraph Checkpoint 表；项目兼容当前 MySQL 8.0.12。

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

## 3. 配置千问、高德与 MCP

在 `.env` 填写：

```text
DASHSCOPE_API_KEY=阿里云百炼API Key
AMAP_API_KEY=高德Web服务Key
AUTH_SECRET=一个足够长的随机字符串
```

需要强制所有 Web API 登录时设置 `AUTH_REQUIRED=true`；本地学习阶段默认允许匿名使用。

| 环境变量 | 国内服务 | 获取位置 | 用途 |
|---|---|---|---|
| `DASHSCOPE_API_KEY` | 阿里云百炼 | [百炼控制台](https://bailian.console.aliyun.com/) | 千问对话、工具调用 |
| `AMAP_API_KEY` | 高德开放平台 | [应用与 Key](https://console.amap.com/dev/key/app) | 地理编码、POI、天气、路线 |
| `FEISHU_VERIFICATION_TOKEN` | 飞书开放平台 | 飞书应用事件订阅配置 | 验证入站 Webhook |
| `FEISHU_ENCRYPT_KEY` | 飞书开放平台 | 飞书应用事件订阅配置 | 校验回调签名 |
| `FEISHU_MCP_URL` | 飞书官方 MCP | `https://mcp.feishu.cn/mcp` | 远程 MCP 文档工具 |
| `FEISHU_APP_ID/SECRET` | 飞书开放平台 | 自建应用凭证 | 自动获取并刷新官方 MCP 的 tenant token |

默认模型与中国北京地域兼容地址已经配置：

```text
MODEL_NAME=qwen3.5-plus
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

启用 MCP：

```powershell
Copy-Item config\mcp.example.json config\mcp.json
```

编辑 `config/mcp.json`，把目标 Server 的 `enabled` 改为 `true`。URL 与 Token 只填写在 `.env`，JSON 中只保存环境变量名。

官方飞书远程 MCP 使用固定地址 `https://mcp.feishu.cn/mcp`。配置
`FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 后，TravelMind 会自动获取并缓存两小时有效的
`tenant_access_token`，通过 `X-Lark-MCP-TAT` 认证。`allowed_tools` 是必填白名单；
当前示例启用官方文档工具 `fetch-doc`。运行以下命令可安全检查连接，不会输出凭证：

```powershell
cd backend
python scripts/check_mcp.py
```

需要文档写入、日历和机器人发消息时，启用 `config/mcp.example.json` 中的
`lark_openapi` stdio Server。它固定使用官方 `@larksuiteoapi/lark-mcp@0.5.1`，
通过子进程环境变量读取 App 凭证，并只开放 `.env.example` 中列出的七个工具。
工具名包含 `create` 的操作会自动进入 Harness 审批，不会静默写入飞书。

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
GET  /chat/{thread_id}/history
GET  /chat/{thread_id}/events
GET  /approvals/{thread_id}
POST /approvals/{thread_id}
POST /trips
GET  /trips
GET  /trips/{trip_id}
POST /trips/{trip_id}/items
GET  /trips/{trip_id}/items
POST /trips/{trip_id}/archive
PATCH/DELETE /trips/{trip_id}
PATCH/DELETE /trips/{trip_id}/items/{item_id}
GET  /trips/{trip_id}/map
POST /auth/register
POST /auth/login
GET  /automations
POST /webhooks/feishu
```

## 5. 运行验收

```powershell
cd backend
python -m ruff check app tests
python -m pytest -q
```

启动服务后运行 20 条真实 Agent 评测：

```powershell
python scripts/evaluate.py
```

运行状态可通过 `GET /metrics` 查看，模型、高德和飞书 MCP 就绪情况通过
`GET /integrations` 查看。

若 Windows 沙箱禁止创建子进程，只有真实 stdio MCP 测试会出现 `WinError 5`；在普通终端运行即可。

## 当前边界

- 飞书消息、文档和日历代码链路已接通；真实写入仍取决于飞书开放平台权限、事件订阅和可访问的 HTTPS 回调地址。
- 第一版不做自动付款、抢票、非官方个人微信登录、多 Agent、微服务、Redis或向量数据库。
- 按当前项目范围不提供 Docker Compose、CI/CD 或云端部署配置。

## 文档导航

1. [产品需求文档](docs/01-product-requirements.md)
2. [详细架构设计](docs/02-architecture-design.md)
3. [Harness 与 MCP 设计](docs/03-harness-and-mcp-design.md)
4. [实现流程与里程碑](docs/04-implementation-roadmap.md)
5. [项目驱动学习路线](docs/05-project-learning-guide.md)
6. [数据模型、接口与测试](docs/06-data-api-testing.md)
7. [项目结构与模块职责](docs/07-project-structure.md)
