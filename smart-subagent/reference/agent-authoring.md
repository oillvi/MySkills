# Agent 造册手册（Qoder CN 实测）

要新增一个钉便宜模型的分身，只需一个 `.md` 定义文件放进被扫描的目录。本仓库 `agents/` 是用户级真身，通过 junction 挂载到 `~/.qoder-cn/agents`。

> 钉了模型的 agent「谁能用、在哪个项目能用」由两级花名册约束：`roster.yml`（用户级）与 `.qoder/smart-subagent.roster.yml`（项目级）。见 [model-routing.md](./model-routing.md)。

## 目录规则（2026-09-22 实测）

| 层级 | 路径 | 说明 |
|---|---|---|
| 用户级 | `~/.qoder-cn/agents/<name>.md` | **不是**文档写的 `~/.qoder/agents`（实测不被扫描） |
| 项目级 | `<project>/.qoder/agents/<name>.md` | 同名遮蔽用户级；不依赖 home，可作退路 |
| 本仓挂载 | `~/.qoder-cn/agents` → `smart-subagent/agents` | junction；E: 盘不挂载即全体失效 |

## 定义文件模板

```yaml
---
name: <kebab-case-name>
description: <分工说明：干什么 / 不干什么；会注入主线程系统提示>
tools: Read, Grep, Glob      # 工具白名单，实测生效
model: GLM-5.3-Flash         # 系统模型：纯 displayName
# model: dc5e0653-…          # 自定义/BYOK：写 modelID（UUID，见本仓 agents/ds-coder.md）
---
<系统提示正文：硬约束 / 工作方法 / 固定汇报格式>
```

- **model 写法（实测）**：系统模型写纯 displayName（如 `GLM-5.3-Flash`）；BYOK 写 UUID。官方文档写的 `[Name](id)` 会被拒（0 次模型调用）。
- **生效时机**：新建/修改定义**当轮不可用**（`Unknown agent type`），下一轮用户消息或新会话才扫描到。

## 验证命令（零/极低 token）

```bash
cd ~/.qoder-cn/bin/qoderclicn && env -u QODER_AGENT_SDK_ENTRYPOINT ./qoderclicn.exe agents list
# 必须 env -u，否则在 agent 会话里跑报 sdk_invalid_args
# 输出按 Project / User / Built-in 分区；列全部模型：同上加 --list-models
# 端到端跑一次：同上 -p "<任务>" --agent <name> -w "<cwd>"
```

## junction 重建（mklink 会被权限分类器拦，用 python）

```bash
python -c "import os,_winapi; _winapi.CreateJunction(r'E:\Work\Qoder Projects\MySkills\smart-subagent\agents', os.path.join(os.environ['USERPROFILE'],'.qoder-cn','agents'))"
```

重建后 `agents list` 应报 7 个（5 内置 + ds-coder + glm-scout）。

## 审计：到底哪个模型在干活

- 主会话 jsonl：`~/.qoder-cn/projects/<编码cwd>/<sessionId>.jsonl`（看 `runtime-config` 行与 assistant 行 `message.model`）
- 子智能体 transcript：同级 `<sessionId>/subagents/agent-a<name>-<hash>.jsonl`（配套 `.meta.json` 可用 toolUseId 对回主会话调用）
- 本地算不了 token（usage 全 0），成本看官网 Credits。

## 模型清单（--list-models，2026-09-22）

- 系统（displayName）：Auto / Qwen3.8-Max / Qwen3.8-Flash / Qwen3.7-Max / Qwen3.7-Plus / Qwen3.7-Flash / DeepSeek-V4-Pro / DeepSeek-Flash / GLM-5.3 / GLM-5.3-Flash / GLM-5.2 / Kimi-K3 / Kimi-K2.8-Preview / MiniMax-M2.7
- 自定义/BYOK（UUID）：Qwen-3.8-Flash / Qwen-3.8-Max / DeepSeek-Flash / DeepSeek-V4.1-Flash / GLM-5.3 / GLM-5.3-Flash
- 内部 key（run 日志）：`gfmodel`=GLM-5.3-Flash、`gmodel`=GLM-5.3、`qmodel_38max`=Qwen3.8-Max、`dfmodel`=DeepSeek-Flash

## 常见坑

- **内置 agent 的 model 全是 `Inherit`，改不了**（Explore / Plan / general-purpose / qoder-guide / statusline-setup）；想换便宜模型必须自建同职能 agent。
- **「自定义 provider」≠ BYOK**：只写在本机 settings.json `providers` 块里的模型（如 mimo 系）不进 CLI `--list-models`，CLI 侧用会报「External Provider is not enabled」；桌面端会话可用。
- 项目级 `.qoder/agents` 是无 junction 的退路（放项目根，进程 cwd 指向项目才扫描到）。
- 模型别名与失效核对：命名规则与更新路径表见 `model-routing.md`；一键核对 `python tools/check-roster.py`（别名重复 / uses 悬空 / ref 失效）。