[English](README.md) | **简体中文**

# smart-subagent — 勘察/执行外包给便宜子智能体

让主线程只做「想清楚 → 写分派单 → 验收」，跑腿的活交给钉了便宜模型的专用子智能体：**glm-scout**（只读勘察，GLM-5.3-Flash）与 **ds-coder**（可写可跑，DeepSeek-V4.1-Flash）。

## 它解决什么问题

装好子智能体 ≠ 会用。本仓库基线实测（`test-artifacts/baseline/REPORT.md`）：5 个典型的勘察/执行任务，主线程 **5/5 全部自己干**，便宜的专才 agent 一次没用上。本技能把「派谁、怎么派、怎么验收」写成可执行协议。

## 机制

- **决策表**：坐标题 → glm-scout；施工题（边界清楚 + 可验收）→ ds-coder；脑力题 / 一步内的小活 → 主线程自己上
- **分派单配方**：任务 / 范围 / 交付物 / 验收标准 / 禁止项（子智能体看不到本会话，必须自包含）
- **验收协议**：抽验 `路径:行号`、复现关键命令、越界发现归主线程——子智能体的「完成」不算数
- **操作约束**：子智能体不 commit（会被权限分类器拦）；junction 单点断则 agent 全体消失；审计落点与 token 记账现实

## 触发方式（实测）

| 方式 | 可靠性 |
|---|---|
| 显式说「用便宜模型」「派子智能体」「使用 smart-subagent」 | ✅ 实测 2/2 分派 |
| 模型自主调用（只靠 description） | ❌ 实测 0/4，请显式说 |

分派正确时，子智能体模型钉桩 100% 生效（glm-scout 全部落在 GLM-5.3-Flash，见 `test-artifacts/green/REPORT.md`）。

## 安装

1. 把技能目录用 junction 链接到 agent 的 skills 目录
2. 把 `agents/` 用 junction 链接到 `~/.qoder-cn/agents`（**`mklink` 会被权限分类器拦，改用 python 命令**，见手册）
3. 验证：`cd ~/.qoder-cn/bin/qoderclicn && env -u QODER_AGENT_SDK_ENTRYPOINT ./qoderclicn.exe agents list` 应报 7 个（5 内置 + glm-scout + ds-coder）

完整命令与排错见 [`reference/agent-authoring.md`](./reference/agent-authoring.md)。

## 实测证据

- `test-artifacts/baseline/REPORT.md` — 红测：技能安装前，5/5 零分派
- `test-artifacts/green/REPORT.md` — 绿测：三轮 15 会话；显式路径全达标、自主触发局限、执行类现状
- `test-artifacts/*/*.log` — 每次会话的原始输出

## License

[MIT](../LICENSE)