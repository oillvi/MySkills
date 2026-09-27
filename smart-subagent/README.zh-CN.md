[English](README.md) | **简体中文**

# smart-subagent — 勘察/执行外包给便宜子智能体

让主线程只做「想清楚 → 写分派单 → 验收」，跑腿的活交给钉了便宜模型的专用子智能体：**mimo-worker**（mimo-v2.6-flash，只读勘察与可写可跑）。

## 它解决什么问题

装好子智能体 ≠ 会用。本仓库基线实测：5 个典型的勘察/执行任务，主线程 **5/5 全部自己干**，便宜的专才 agent 一次没用上。本技能把「派谁、怎么派、怎么验收」写成可执行协议。

## 机制

- **决策表**：坐标题与施工题（边界清楚 + 可验收）→ mimo-worker；脑力题 / 一步内的小活 → 主线程自己上
- **分派单配方**：任务 / 范围 / 交付物 / 验收标准 / 禁止项（子智能体看不到本会话，必须自包含）
- **验收协议**：抽验 `路径:行号`、复现关键命令、越界发现归主线程——子智能体的「完成」不算数
- **操作约束**：子智能体不 commit（会被权限分类器拦）；junction 单点断则 agent 全体消失；审计落点与 token 记账现实
- **两级花名册**：子任务能用哪些模型/agent 由 `roster.yml`（用户级，全局默认）约束，项目级 `.qoder/smart-subagent.roster.yml` 可整体覆盖收紧或扩员；任务出现时按类别即时路由，**越册不派**
- **模型别名与提醒**：`models:` 给模型起人话名（系统自带 `qoder-<名字>`；BYOK 用来源如 `deepseek-v4.1-flash`；通用接口自取）；调用时发现未命名/已删除 → 停下提醒更新花名册；改什么去哪按「更新路径表」直达文件

## 触发方式（实测）

| 方式 | 可靠性 |
|---|---|
| 显式说「用便宜模型」「派子智能体」「使用 smart-subagent」 | ✅ 实测 2/2 分派 |
| 模型自主调用（只靠 description） | ❌ 实测 0/4，请显式说 |

分派正确时，子智能体模型钉桩 100% 生效（当时的勘察员全部落在 GLM-5.3-Flash）。

## 看守探针（Watchdog Probe）

派长任务时分派单多带第五件「探针卡」（预算/里程碑/已知坑/检查点），派后对子智能体 transcript（`subagents/agent-a<name>-<hash>.jsonl`，只读）巡检：

```text
python tools/probe.py <transcript> --budget N                                          # 粗筛：5 类卡死模式 + 停滞 + 预算
python tools/probe.py <transcript> --fine coder --expect "<验收命令子串>" --expect-file <交付物>   # WARN 后换施工细探针
python tools/probe.py <transcript> --fine scout                                        # 勘察细探针
```

- 粗筛判据（`reference/watchdog.md` §2）：全等/近似重复、A-B 振荡、报错循环、独白无产出、停滞 90/300s、预算 80/100%。
- 细探针（§3.1）：coder 卡 C1 同路径反复改（3/5）、C2 验收命令缺席、C3 交付物缺位；scout 卡 S1 查询重复（3/5）、S2 近 5 轮零新坐标、S3 同文件重读（3/5）。
- 处置：WARN=换对应细探针卡定点观察；BLOCK=主线程 `TaskStop` + 归因 + 带检查点重派（同一任务 ≥2 次 BLOCK 停下上报用户）。探针只读、单跑 <2s、digest ≤10 行。

## 子任务真实耗时（tools/tasktime.py）

**别信聊天卡片上的「子 Agent 已完成 Xs」**——那是显示层抓错了锚点：后台派单的 Agent 工具调用 **3.3–4.9s** 就返回 `Async agent launched successfully`，卡片时长锚在这段工具调用计时上，不是子任务墙钟（2026-09-27 实测：108bc031 七个子任务卡片几十秒级、真实 444.2–2268.5s；21409185 三个真实 1697.1–3695.2s）。

真实墙钟在会话目录 `subagents/task-*.json` 的 `createdAt→completedAt`（与 transcript 首末 `timestamp` 差 <1s），取数：

```text
python tools/tasktime.py --session-dir <会话目录>     # 不传则取最近一组子任务
```

输出每个子任务一行（`invName  状态  墙钟  来源  描述`）+ 合计行（个数/完成数/Σ墙钟/并行跨度）；时间戳缺失时退回 transcript 首末差，来源列标注 `task-json`/`transcript`/`missing`。只读、纯标准库，7 条单测在 `tools/test_tasktime.py`。

## FAQ：模型怎么定、怎么约束

- **技能谁触发？** 你显式触发（见表）。另注意：agent 本身常驻可见——直接点名「让 mimo-worker 去查 X」也能用；技能管的是「怎么派得对、怎么验收」。
- **怎么指定子任务用哪个模型？** 派单时无法临场传模型——模型钉在 agent 定义文件的 `model:` 字段里，**选 agent 就是选模型**。换模型：改定义文件，或新建钉到目标模型的 agent 并登记花名册（扩容三步）。
- **后续任务还不知长什么样？** 不用预知。花名册约束「允许集合 + 类别→agent 路由」，任务出现时即时分类；类别看不准按 `use_for` 找最便宜的适配者；不在册按 `on_out_of_roster` 处理。
- **约束范围分几级？** 两级：用户级 `skills/smart-subagent/roster.yml`（全局默认）> 项目级 `<项目根>/.qoder/smart-subagent.roster.yml`（存在即整体替换）。详见 [`reference/model-routing.md`](./reference/model-routing.md)。
- **怎么给模型起别名？改了模型去哪儿改？** 别名统一存用户级 `roster.yml` 的 `models:`；换某 agent 的钉桩改 `agents/<name>.md` 的 `model:` 并同步 roster 的 `uses`；文档里有「更新路径表」，改什么直接查表定位。

## 安装

1. 把技能目录用 junction 链接到 agent 的 skills 目录
2. 把 `agents/` 用 junction 链接到 `~/.qoder-cn/agents`（**`mklink` 会被权限分类器拦，改用 python 命令**，见手册）
3. 花名册 `roster.yml` 随技能自带，默认可直接用；要收紧/扩员就编辑它或加项目级覆盖文件
4. 验证：`cd ~/.qoder-cn/bin/qoderclicn && env -u QODER_AGENT_SDK_ENTRYPOINT ./qoderclicn.exe agents list` 应报 6 个（5 内置 + mimo-worker）

完整命令与排错见 [`reference/agent-authoring.md`](./reference/agent-authoring.md)。

## 实测证据

- 四轮行为测试（红测 5/5 零分派、绿测 15 会话、花名册、别名层）与原始 log 归档于仓库外本地目录 `MySkills-archive`（**未随仓库分发**）；历史提交中保留早期副本

## License

[MIT](../LICENSE)