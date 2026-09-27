---
name: smart-subagent
description: 先调用本技能再动手：当本轮任务含可外包的块——勘察类（找出/列出/统计/定位/梳理/追踪引用/翻文档）或执行类（批量改/写脚本并跑通/修好并验证）——就把它们交给钉了便宜模型的子智能体（mimo-worker）干，而不是主线程自己干；出现「派子智能体」「用便宜模型」「跑个腿」「mimo-worker」等说法同样先调用本技能。设计与一步内的小改动不适用。Use when a turn contains a separable scouting or execution block (find/list/count/locate/trace docs/batch edit/write-and-run/fix-and-verify) worth handing to a pinned cheap subagent instead of doing inline.
---

# Smart SubAgent（主线程只做编排与验收）

主线程（贵模型）负责：想清楚 → 写分派单 → 验收。子智能体（钉了便宜模型的专用 agent）负责：跑腿与执行。**装了 agent 不等于会用**——基线实测里主线程把活全包了（证据存本地归档，未随仓库分发），本技能就是修这个。

**动手前先自检**：本轮有没有够格外包的块（≥3 次工具调用才能收敛的勘察 / 有界且可验收的执行）？有 → 先读有效花名册（见第 1 节末），再按第 2 节写分派单，派给在册 agent；没有 → 直接做，别硬派。

## 1. 派谁（决策表）

| 任务块 | 派谁 | 触发信号 |
|---|---|---|
| 只读勘察：定位文件/符号/引用、查配置来源 | **mimo-worker**（mimo-v2.6-flash，只读勘察） | 预期 ≥3 次搜索，或答案分散在 ≥5 个文件；一句话说不清坐标 |
| 有界执行：改代码/写文件/跑脚本/批量改名 | **mimo-worker**（mimo-v2.6-flash，可写可跑） | 边界能一句话说清，且验收标准可执行（跑什么、看到什么算过） |
| 设计/需求探索/方案对比 | **不派**，主线程自己做 | 需要主上下文判断、要来回澄清 |
| 小活（一次编辑内完成） | **不派**，顺手做掉 | 改一个常量、加一行、改个词 |
| 跨多轮交互的任务 | **不派**（子智能体只跑单轮） | 需要追问用户、依赖前文 |

口诀：**勘察施工都派 mimo-worker，脑力题自己上，顺手活别折腾。** 拿不准先派一轮 mimo-worker（便宜），拿到证据再定下一步。

### 谁可用：两级花名册（模型约束）

子任务用哪个模型**不是分派时现挑的**——模型钉死在每个 agent 的定义文件里（见 `reference/agent-authoring.md`）；派单时只能「选 agent」，选了 agent 就等于选了模型。能选谁由两级花名册约束，**生效顺序：项目级 > 用户级 > 本节默认员（mimo-worker）**：

| 级别 | 文件 | 作用 |
|---|---|---|
| 用户级 | `~/.qoder-cn/skills/smart-subagent/roster.yml`（真身=本仓 `roster.yml`） | 全局默认：所有项目可用的 agent/模型 + 类别→agent 路由表 |
| 项目级 | `<项目根>/.qoder/smart-subagent.roster.yml` | 存在即**整体替换**用户级，用于收紧或扩员 |

路由规则（任务出现时才分类，不用预知）：

1. 类别命中 `routing` 映射 → 派对应 agent。
2. 类别看不准 → 按各 agent 的 `use_for` 找最便宜的适配者；没有适配者就不派（顺手做或上报）。
3. 需要的能力不在册 → 按 `on_out_of_roster` 行事（`report`=停下报告；`inline`=主线自己干）；**绝不越册派**。
4. 用户当轮点名（「派 mimo-worker」「别派」）→ 用户指令优先。

**别名与失效提醒**：`models:` 段给模型起了别名（系统自带 `qoder-<名字>`、BYOK 用来源如 `deepseek-v4.1-flash`、通用接口自取）。派单/换模型时遇到：别名未入册、`uses` 悬空、或 ref 已失效（模型被删/撤销）→ **停下提醒用户更新花名册**（写明改哪个文件），不要猜着用或静默换别的模型。核对命令：`python tools/check-roster.py`。

**改花名册别全仓搜**：按 `reference/model-routing.md` 的「更新路径表」（改什么→去哪）直达目标文件。

花名册是派单前现读的普通文件，改完立即生效；新增 agent 定义才要等下一轮。字段说明与扩容三步见 `reference/model-routing.md`。

## 2. 分派单配方

子智能体看不到本会话上下文。分派提示词必须自包含，四件套缺一不可：

```text
任务：<一句话，动词开头>
范围：只动 <具体路径/文件>；其他一律不碰
交付物：<报告 / 文件改动 / 命令输出>
验收标准：<跑什么命令、看到什么算过；或：报告须含 路径:行号 证据>
禁止项：不 git 提交、不 push、不改范围外文件、不装依赖（除非明确允许）
汇报格式：按你定义文件里的固定格式回报
```

- 边界写「只做 X」，不用「别做 Y」清单（禁项只放硬红线）。
- 依赖子智能体自带的汇报格式（mimo-worker：结论/改了什么、怎么验的、越界发现、遗留）。
- 多个独立只读块可并行派多个在册 agent 实例；写操作串行，别并发改同一片文件。
- **便宜模型的分派单要逼它先动手**：写明「直接动手、工具调用之间说明 ≤1 行、汇报 ≤8 行」并拆小步（如先脚本本体后单测）——实测 mimo-v2.6-flash 拿到大分派单会把输出烧在长篇分析上（整发报废、零写入）。
- **长任务附探针卡**（字段见 `reference/watchdog.md` §0：预算/里程碑/已知坑/检查点）：派后按巡检节奏对 `subagents/agent-a<name>-<hash>.jsonl` 跑 `python tools/probe.py <transcript> --budget N`——OK 继续、WARN 按 `reference/watchdog.md` §3.1 细探针模板（coder/scout）换卡定点观察、BLOCK 交主线程处置（见第 4 节）。

## 3. 验收协议（子智能体的「完成」不算数）

1. **核对坐标**：抽 1–2 条 `路径:行号` 用 Read 核实（子智能体报告尤其防幻觉）。
2. **复现验证**：子智能体报的验证命令，重跑关键一条；对不上就退回。
3. **越界发现归主线程**：要么进待决项，要么派新一轮，别顺势改。
4. **只采信证据**：子智能体的动作与证据入账；它的「建议/最佳实践」不采信。
5. **汇报固定带子任务耗时行**：凡派过子智能体的轮次，给用户的汇报（含四段式【结果】）必须带一行 `子任务耗时：<invName> <真实墙钟>，<invName> <真实墙钟>（tasktime.py 口径）`——逐任务一行或一行逗号分隔，数字只取 `python tools/tasktime.py --session-dir <会话目录>`；子智能体自报的耗时只作交叉核对。**不许把聊天卡片「子 Agent 已完成 Xs」的数字写进汇报**（见 §4「卡片时长是碎片」）。

## 4. 操作约束（本机实测，2026-09-22）

- **提交归主线程**：子智能体的 git 提交会被权限分类器拦；分派单明写「不提交」。
- **新定义下一轮才生效**：新建/改 agent 定义，当轮调不到（`Unknown agent type`），下一轮或新会话可见。
- **junction 是单点**：`~/.qoder-cn/agents`（→ 本仓库 `smart-subagent/agents`）一断，自定义 agent 全体消失（`agents list` 只剩 5 个内置）。重建用 python `_winapi.CreateJunction`（`mklink` 会被分类器拦），命令见 `reference/agent-authoring.md`。
- **审计落点**：主会话 `~/.qoder-cn/projects/<编码cwd>/<sessionId>.jsonl`；子智能体 transcript 在同级 `subagents/agent-a<name>-<hash>.jsonl`——查「哪个模型在干活」看这里。
- **本地算不了 token**：系统/BYOK 通道 usage 全为 0，成本只能官网 Credits 核对。
- **「用某模型做 subagent」≠「创建智能体」**：任务里说调用某大模型做 subagent，只在当前会话里选在册 agent 派单（任务级）；新建/修改/删除 agent 定义文件是用户级操作，除非用户明说「创建/改/删某 agent」，否则一律不动。
- **看守处置权归主线程**：probe.py 判 BLOCK 后，安全关闭子任务（TaskStop）与「分析后带 checkpoint 重派」只由主线程执行；子智能体不自杀、不杀他。探针体量红线：只读、单跑 <2s、摘要 ≤10 行。
- **卡片时长是碎片（2026-09-27 实测）**：后台派单的 Agent 工具调用 **3.3–4.9s** 就返回 `Async agent launched successfully`，聊天卡片「子 Agent 已完成 Xs」锚在这段工具调用计时上，**不是**子任务墙钟（108bc031 七个子任务真实 444.2–2268.5s、21409185 三个 1697.1–3695.2s）。真实墙钟在 `subagents/task-*.json` 的 `createdAt→completedAt`（与 transcript 首末 timestamp 差 <1s），取数用 `python tools/tasktime.py --session-dir <会话目录>`。

## 5. 与其他技能的关系

- **不抢触发**：设计类任务照常走 brainstorming / planning；本技能只在出现可外包的勘察/执行块时叠加生效。
- **叠加用法**：先派 mimo-worker 勘出坐标（省主线程上下文），再回到 brainstorming 等流程继续。
- 与 dispatching-parallel-agents / subagent-driven-development 同轮时：它们管「怎么编排多任务」，本技能管「每块派给谁、分派单怎么写、怎么验收」。

## 6. 常见走样

| 症状 | 修法 |
|---|---|
| 装了 agent 不用，主线程全包（基线实测） | 每轮动手前先过第 1 节决策表 |
| 分派单写成「帮我看看 X」 | 补齐四件套：范围/交付物/验收标准/禁止项 |
| 采信子报告直接收工 | 走第 3 节验收协议（抽验坐标 + 复现命令） |
| 顺手小活也派子智能体 | 单次编辑内的活自己做完，别付 spawn 成本 |
| 拿聊天卡片「子 Agent 已完成 Xs」当子任务耗时 | 后台派单 3.3–4.9s 即返回、锚点错位（§4）；改用 `python tools/tasktime.py` 取 `createdAt→completedAt` 真实墙钟 |

## 7. 兜底

- `agents list` 里没有 mimo-worker → 先修 junction；修不了则勘察兜底用内置 Explore，执行兜底用 general-purpose（不省成本，仅保可用）。
- 花名册缺失或要派的不在册 → 退回兜底默认员 mimo-worker；其他 agent 一律不派。
- 子智能体报「未覆盖/验不了」的部分：主线程补位或明说做不到，不掩饰。