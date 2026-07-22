# TravelMind Skills

这里保存 Agent 按需加载的出行领域知识。应用启动时只读取每个 `SKILL.md` 的名称和简介；Agent 调用 `skill.load` 后才把完整规则放入当前上下文。

当前 Skill：

- `budget-travel`：预算分配、机动资金和保存前校验。
- `family-travel`：老人/儿童场景的低强度、休息和步行约束。

Skill 只提供知识与工作方法，不持有密钥、不直接调用外部服务，也不能绕过 Harness Tool Registry 和 Permission Engine。

新增 Skill 时创建 `skills/{name}/SKILL.md`，并在 YAML frontmatter 中填写：

```yaml
---
name: example-skill
description: 一句话说明什么时候加载。
---
```
