# 模型路由与两级花名册（Qoder CN）

子任务的模型 = 该 agent 定义文件里钉死的 `model` 字段（写法见 `agent-authoring.md`）；派单时无法临场指定模型，只能选 agent——**选了 agent 就是选了模型**。能选谁由两级花名册约束：

| 级别 | 路径 | 语义 |
|---|---|---|
| 用户级 | `~/.qoder-cn/skills/smart-subagent/roster.yml`（真身=本仓 `roster.yml`，junction 挂载） | 全局默认，所有项目生效 |
| 项目级 | `<项目根>/.qoder/smart-subagent.roster.yml` | 存在即**整体替换**用户级；用于收紧或扩员 |

生效顺序：**项目级 > 用户级 > 技能内置默认**（glm-scout + ds-coder 两员）。花名册是「派单前现读」的普通文件，**改完立即生效**，不需要新会话。

## 文档地图（按路径找文件，不用全仓搜）

```
smart-subagent/
  SKILL.md               ← 主协议：路由规则 / 分派单 / 验收（第 1 节是花名册规则）
  roster.yml             ← 用户级花名册：别名菜单 models + agent 名单 agents + 路由 routing
  reference/
    model-routing.md     ← 就是本文档：别名命名规则 / 失效提醒协议 / 更新路径表 / 字段表
    agent-authoring.md   ← 造 agent、model 写法、junction 修复、模型全清单
  agents/<name>.md       ← agent 定义真身：实际钉桩（frontmatter 的 model:）
  tools/check-roster.py  ← 核对花名册：别名重复 / uses 悬空 / ref 失效
  test-artifacts/        ← 不随仓库分发；本地归档 MySkills-archive\smart-subagent\test-artifacts\
```

## 模型别名（菜单层）

为什么要别名：模型来自多个厂商、名字/ID 混杂，别名让「派单、换模型、对话」都有一致的短名字。别名统一存**用户级** `roster.yml` 的 `models:` 段（项目级花名册自带自己的菜单）。

| 类别 | 命名规则 | 示例 |
|---|---|---|
| Qoder 系统自带 | `qoder-<名字>`（小写连字符） | `GLM-5.3-Flash` → `qoder-glm-5.3-flash`；`Qwen3.8-Max` → `qoder-qwen3.8-max` |
| BYOK（来源可辨） | `<厂商>-<型号>` | `DeepSeek-V4.1-Flash`（UUID） → `deepseek-v4.1-flash`；`GLM-5.3`（UUID） → `glm-5.3` |
| 通用接口（自定义 provider） | 自取（建议 `<来源>-<型号>`） | `local-mimo-v2.6-flash`、`my-corp-llm` |

菜单默认**全量登记**本机可用模型（系统自带 + BYOK）；通用接口（自定义 provider）按需登记，其 ref 不做 CLI 目录核对——仅桌面端可用。新模型出现时按命名规则补一条入册（见下方提醒协议）。带注释的分区示例见 `roster.yml`。

## 失效与未命名提醒协议（调用时必查）

派单/换模型/被点名要求使用某模型时，按序核对：

1. **别名在册吗？** 不在 `models:` → **停下提醒用户更新花名册**（给出命名规则与目标文件路径），不要猜着用、不要静默换成别的模型。
2. **`uses` 悬空吗？** agent 的 `uses` 指向不存在的别名 → 同上，提醒修 roster 或用 `check-roster.py` 定位。
3. **ref 还有效吗？** 模型可能被下架/撤销（系统目录调整、BYOK 失效）：跑 `python tools/check-roster.py` 核对（或手工 `--list-models` 对照）。失效 → 提醒更新：改 ref 或删条目。

一步到位的核对命令（可复现）：

```bash
python "smart-subagent/tools/check-roster.py"          # 默认核对用户级花名册
python "smart-subagent/tools/check-roster.py" <路径>    # 核对指定花名册（如项目级）
```

## 更新路径表（改什么 → 去哪）

| 你要做什么 | 改这个文件 | 位置 |
|---|---|---|
| 给模型起/改别名、删失效条目 | 用户级 `roster.yml`（真身=本仓 `roster.yml`） | `models:` 段 |
| 增删可派 agent、改类别路由 | 同上 | `agents:` / `routing:` 段 |
| 换某 agent 实际钉的模型 | `agents/<name>.md` | frontmatter `model:`（系统=displayName / BYOK=UUID），并同步 roster 的 `uses` |
| 新增一个钉桩 agent（扩容三步） | 新建 `agents/<name>.md` | 模板见 `agent-authoring.md`；等下一轮生效后登记进 roster |
| 本项目收紧/扩员（只对本项目） | `<项目根>/.qoder/smart-subagent.roster.yml` | 整个文件（整体替换用户级；没有就新建） |
| junction 断了 / 重建 | 见 `agent-authoring.md`「junction 重建」 | python 命令 |
| 改路由协议本身 | `SKILL.md` 第 1 节 + 本文档 | — |

## 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `version` / `level` | 是 | 版本号（v2）/ `user` 或 `project` |
| `models[].alias` / `.ref` / `.kind` | 是 | 别名 / 实际模型（displayName 或 UUID）/ `system` `byok` `custom` |
| `models[].note` | 否 | 备注（如「仅桌面端」） |
| `agents[].name` | 是 | agent 名（`agents list` 里的名字） |
| `agents[].uses` | 是 | 指向 `models[].alias`；实际钉桩以 `agents/<name>.md` 为准 |
| `agents[].class` / `.use_for` | 是 | 任务类别标签 / 一句话适用面 |
| `routing` | 建议 | 类别→agent 映射，命中即派 |
| `on_out_of_roster` | 是 | `report`=停下报告 / `inline`=主线自己干；两种都不允许越册派 |

## 路由协议

1. `routing` 命中 → 派对应 agent。
2. 类别看不准 → 按 `use_for` 找最便宜的适配在册 agent；没有适配者就不派。
3. 需要不在册的能力 → 先走「失效与未命名提醒协议」（提醒补名入册），再按 `on_out_of_roster` 处理。
4. 用户当轮点名 → 用户指令优先。

**未知后续任务不用预知**：花名册约束的是「允许集合 + 路由」，不是具体任务清单；任务出现时即时分类即可。

## 项目级示例（收紧到只许勘察）

```yaml
# <项目根>/.qoder/smart-subagent.roster.yml   （整体替换用户级，菜单要带全）
version: 2
level: project
models:
  - alias: qoder-glm-5.3-flash
    ref: GLM-5.3-Flash
    kind: system
agents:
  - name: glm-scout
    uses: qoder-glm-5.3-flash
    class: scout
    use_for: 定位坐标、追引用、翻文档
routing:
  scout: glm-scout
on_out_of_roster: report   # 编码类任务：停下报告，等用户拍板
```

## 扩容三步（新任务类别反复出现时）

1. 若目标模型还没别名：先在 roster `models:` 命名入册（规则见上）；
2. 按 `agent-authoring.md` 模板新建 `agents/<name>.md`，`model:` 钉到目标模型（系统=displayName / BYOK=UUID）；
3. 新会话（或下一轮）跑 `agents list` 确认可见，再把该 agent 加进 roster 的 `agents:` 与 `routing:`。

## 让它更大程度自动化（可选）

花名册协议依赖会话里「读册」这一步。想更常驻，在本项目 `AGENTS.md`（或你的全局规则）加一行常驻条款，例如：

> 本项目勘察类（≥3 次搜索）与执行类（有界可验收）工作，优先派花名册在册子智能体（见 smart-subagent 技能第 1 节）；设计与小改动留在主线。

## 边界（实测说明）

- 这是**软约束**：靠主线程按规则执行（花名册/别名两轮红绿实测已做，存档在本地归档、未随仓库分发）；Qoder 本身没有「机械禁止某模型」开关。
- 硬边界只有「可见性」：不在册但已安装的 agent 依然可调——必须靠花名册协议拦。
- 别名是**花名册内部约定**，Qoder 不识别别名；换钉仍要落到 agent 定义文件的 `model:`。