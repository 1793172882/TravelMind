# 项目驱动学习路线

## 1. 学习方法

本项目不是先看完所有理论再开发，而是采用循环：

```text
遇到业务问题
→ 学习一个Agent概念
→ 实现最小机制
→ 运行实验
→ 写测试
→ 复盘设计取舍
```

每个主题都要回答四个问题：

1. 它解决了什么真实问题？
2. 没有它时系统会怎样失败？
3. 框架替我们做了什么？
4. 我们自己的Harness还要做什么？

## 2. Agent基础

### 必须掌握

- LLM、Agent和Harness的区别。
- System、User、Assistant、Tool消息。
- Tool Calling循环。
- Prompt不是业务状态数据库。
- Temperature、Token、上下文窗口的基本影响。

### 项目实验

- 用相同模型分别运行“无工具”和“有工具”的预算问题。
- 故意把工具描述改得含糊，观察工具选择变化。
- 删除Tool Result回传，观察Agent为什么不能继续。

### 完成标准

能够不看代码画出模型—工具循环，并解释Harness处于哪个位置。

## 3. LangChain

### 必须掌握

- `create_agent`。
- Tool及输入Schema。
- `state_schema`和`context_schema`。
- Middleware生命周期。
- Structured Output策略。
- 同步、异步和流式调用。

### 项目实验

- 用Fake模型测试一次Tool Call。
- 在Middleware中记录工具耗时。
- 让Agent输出Pydantic行程对象。

### 完成标准

可以解释为什么不再手写第二套Agent Loop，以及哪些逻辑不应放进Prompt。

## 4. LangGraph

### 必须掌握

- State、Node、Edge和Command。
- Checkpointer与 `thread_id`。
- Store与Checkpoint区别。
- `interrupt()`和恢复。
- Stream events。
- Durable execution的边界。

### 项目实验

- 在创建日历前中断。
- 关闭并重启进程后批准。
- 使用两个 `thread_id` 验证状态不串线。

### 完成标准

可以解释“会话历史”“执行现场”“业务行程”“用户长期记忆”为什么要分开保存。

## 5. Tool工程

### 必须掌握

- 工具粒度和命名。
- Schema验证。
- 超时、重试、限流和幂等。
- 外部数据标准化。
- 并行调用的适用条件。
- 数据来源和时间戳。

### 项目实验

- 给路线接口注入超时。
- 给相同写操作调用两次，验证不会重复创建。
- 比较直接返回原始JSON和返回精简模型的Token消耗。

## 6. 权限与安全

### 必须掌握

- Trust Boundary。
- ALLOW、ASK、DENY。
- 凭证隔离。
- Prompt Injection对工具调用的影响。
- 审计与最小权限。

### 项目实验

- 让工具结果包含“忽略规则并发消息”的恶意文本，验证不会绕过权限。
- 尝试让模型读取密钥，验证工具和Prompt中不存在密钥。
- 验证拒绝审批后原写操作不会自动重试。

## 7. 上下文与记忆

### 必须掌握

- 短期上下文和长期记忆。
- Selection、Extraction、Consolidation。
- 工具结果预算。
- 摘要丢失事实的风险。
- 用户隔离和隐私。

### 项目实验

- 构造超长地点搜索结果。
- 压缩前后比较Token数和约束保留率。
- 修改用户步行偏好，验证旧记忆被更新而非重复追加。

## 8. MCP

### 必须掌握

- Host、Client、Server。
- stdio和Streamable HTTP。
- Initialize与能力协商。
- `tools/list`和`tools/call`。
- Session生命周期。
- MCP工具仍需Harness权限治理。

### 项目实验

- 建立本地Fake MCP Server。
- 运行时发现两个工具。
- 模拟Server退出并验证其他工具仍可使用。
- 将同名工具置于不同命名空间。

### 完成标准

可以解释为什么MCP属于Harness，以及为什么一个MCPManager内部仍然有多个Client Session。

## 9. Background与Scheduler

### 必须掌握

- 请求内异步与持久后台任务的区别。
- Job持久化。
- Outbox Pattern。
- 重复执行和幂等。
- Fake Clock测试。

### 项目实验

- 模拟服务在定时任务触发前重启。
- 模拟飞书发送失败后恢复。
- 同一Job执行两次，验证没有重复日历事件。

## 10. 评测

Agent测试不能只判断一句文本是否完全相同，应分层：

```text
单元测试：金额、时间、距离、Schema
工具测试：参数、超时、标准化、幂等
轨迹测试：是否调用了正确工具
状态测试：Checkpoint、审批、恢复
任务评测：最终行程是否满足约束
安全测试：未经审批不得外部写入
```

### 最小评测集

- 普通一日游。
- 带老人和步行限制。
- 预算不足。
- 下雨替换户外项目。
- 地点营业时间冲突。
- 地图接口超时。
- MCP Server断开。
- 飞书写入被拒绝。
- 服务重启后继续。
- 恶意工具结果注入。

## 11. 每阶段复盘模板

完成一个里程碑后，在开发日志中回答：

```text
本阶段解决的问题：
最小实现：
没有使用的复杂方案：
一次真实失败：
自动化检查：
当前限制：
什么时候需要升级：
```

## 12. 面试表达训练

不要只说“使用了LangChain和LangGraph”，而要说：

```text
问题：外部写入可能在用户未确认时执行。
设计：所有工具统一进入Permission Middleware。
实现：高风险工具触发LangGraph interrupt，并通过Checkpoint持久化。
验证：进程重启后恢复审批，拒绝后不会执行原工具。
结果：测试集中未经审批的高风险调用为0。
```

每一个技术亮点都用“问题—设计—实现—验证—结果”表达。

## 13. 推荐资料顺序

1. `learn-claude-code` 当前 `s01-s20`，理解Harness机制。
2. LangChain v1 Agent、Middleware、Structured Output官方文档。
3. LangGraph Persistence、Memory、Interrupt和Streaming官方文档。
4. MCP Architecture、Client与Transport官方文档。
5. 飞书开放平台新版文档、日历和多维表格文档。

不要同时学习多个Agent框架。当前项目只以LangChain/LangGraph为主。

