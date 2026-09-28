# outbox-recorder 设计规格

- 日期：2026-09-28
- 状态：已批准（Q1–Q6 逐题裁定，用户指示跳过 writing-plans 直接实现）
- 落点：`E:\Work\Qoder Projects\MySkills\DSH improve\outbox-recorder\`（本仓库存放真身，交付到内网机）
- 运行环境：**另一台**内网离线机上的 DSH Desktop，模型为本地部署的 `qwen3.8-max 27B`（小规模）
- 本机不是运行环境，只是编写与验证台

## 1. 目的

内网机上的 DSH 用 arcadia-1 技能包驱动 Cadence Virtuoso 做模拟／数模混合芯片开发。该机无外网、模型能力有限且易跑飞。本技能让离线 agent 把以下东西写成 Markdown，由人肉摆渡到外网侧处理：

1. 撞到的问题（工具报错、流程卡死）
2. 想要但当前没有的能力
3. 效率或精度瓶颈
4. 需要从外网获取的资料或任何东西
5. 自己察觉的跑飞事件
6. 自己提议的改进方向（供人裁决是否建新技能）

**硬红线**：严禁记录 Cadence 库数据（PDK model card、tech file、DRC/LVS rule deck、库/单元定义、厂商绝对路径）。只允许引用当前项目自己的网表作为辅助证据。

## 2. Q1–Q6 裁定

| # | 裁定 | 依据 |
|---|---|---|
| Q1 | 与 arcadia-1 同一个 DSH 发现根，平级 | 用户选 (a) |
| Q2 | 红线取 (ii)：master 名也占位化；两道机守 | 用户选 (ii)＋两道机 |
| Q3 | 载体取 (A)：每条一文件 write-once，ID／归位／清单全归脚本 | DSH `write` 无 append 模式；27B 做 read-modify-write 必截断历史 |
| Q4 | 落点 (A)：技能树独立于 analog-agents 仓库；携出 (ii) `git bundle`；回执走 `inbox/` 由脚本合并 | 实测 analog-agents `.gitignore:50` 的 `references/` 会吞任意深度的同名目录；`skills/*/_local/` 有被整目录重拷删掉的风险 |
| Q5 | 内网模型 `qwen3.8-max 27B`，小规模 | 用户明确「不是本机那个大规模 qwen3.8-max」 |
| Q6 | 提案取 (i)：只写「问题＋改进方向」，不产 SKILL.md 草案；强制 `derived_from` 派生＋同类去重 | analog-evolve 既有范式是「限定填空，不让它设计」；DSH frontmatter 硬校验且失败静默跳过 |

## 3. 目标运行时的实测契约

来自 DSH Desktop 2.0.15 / harness `@deepseek-ai/dsh` 0.1.7-rc.2 的源码（`dsh-skill-filesystem`、`dsh-skill`、`dsh-tool-skill`、`dsh-tool-fs`）。

- **发现根优先级**：`<项目根>/.dsh/skills`(100) > `.agents/skills`(200) > `Config.customSkillDirs`(300) > `~/.dsh/skills`(400) > `~/.agents/skills`(500) > `$DSH_BUNDLED_SKILL_DIR`(600)。项目根＝向上找 `.git`。
- **布局**：只认 `<根>/<目录>/SKILL.md` 或 `<根>/<名>.md`，**最深 2 段**。`scripts/`、`references/` 不会被当技能，也不会自动加载，只在资源提示里给一行 base directory。
- **frontmatter 认的字段**：`name`（须匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$`）、`description`（catalog 截断 500 字符）、`whenToUse`（只认驼峰）、`disable-model-invocation`、`user-invocable`、`metadata`。
- **静默忽略**：`allowed-tools`、`model`、`version`、`license`、`argument-hint`。
- **直接抛错**：`disableModelInvocation`、`modelInvocable`、`userInvocable`。
- **失败行为**：一律 `logger.warn` ＋ 静默跳过该文件，模型侧完全看不到。
- **渐进披露**：只有 `name`＋`description` 每轮进 catalog；正文在模型调 `skill` 工具时整篇返回，无截断。
- **工具名全小写**：`read` `write` `edit` `glob` `grep` `bash` `pwsh` `skill` `todo_write` `web_search` `web_fetch`。`str_replace_editor` 在 bundle 里但**未挂进 standard preset**，不可依赖。
- **`write` 只能整文件替换，没有 append 模式。**

结论：本技能只用 `read`／`write`／`edit`／`bash` 四个工具，且**永不 append**。

## 4. 目录布局

```
<DSH 发现根>/outbox-recorder/
├── SKILL.md
├── scripts/
│   ├── outbox.py          # 主 CLI；记录模板内嵌为字符串
│   ├── guard.py           # 第二道机：库数据检测器
│   └── sanitize_bridge.py # 第一道机：接 arcadia-1 的 sanitize_text，找不到降级
├── references/
│   ├── record-schema.md
│   ├── guard-rules.md
│   └── install.md
├── records/{problem,wish,bottleneck,need-outside,drift,skill-proposal}/
├── drafts/
├── inbox/                 # 回执；处理完移入 inbox/_done/
├── _local/                # 永不外携、不进 git
│   ├── own-cells.txt      # 本项目自有 cell 白名单（用户维护）
│   ├── cell-map.yml       # 真名 → 占位符，脚本追加，跨记录稳定
│   └── config.yml         # python 解释器、arcadia-1 根、项目名
├── MANIFEST.md
├── index.jsonl
└── .gitignore
```

`records/` 进 git（bundle 即运输工具）；`_local/`、`drafts/`、`inbox/_done/`、`__pycache__/` 不进。
ID 不靠计数器文件：`commit` 时扫 `records/*/` 取同前缀最大号＋1，无状态可丢。

## 5. 记录 schema

文件名照 arcadia-1 `AGENTS.md:108-114`（段内单 `_`、段间双 `__`）：
`records/problem/20260928_143502__prob-0007__<slug>.md`

ID 前缀沿用 `wiki-schema.md` 风格：`prob-` `wish-` `bneck-` `need-` `drift-` `prop-`，四位补零。

frontmatter 字段：`id` `type` `status` `created` `project` `block` `severity` `effort_seen` `related_wiki` `derived_from` `recurrences` `env{harness,desktop,arcadia1_sha,model}`。

- `status`：`pending-review` → `approved` / `rejected` / `answered` / `wontfix`
- `severity`：`blocking` / `slowing` / `annoyance`
- 必填：`id` `type` `status` `created` `project` `severity`，正文的 现象／已试过／期望的答案长什么样
- `derived_from`：仅 `skill-proposal` 必填，须指向真实存在的 `drift` 或 `problem` 记录
- 上限：正文 ≤200 行，证据网表 ≤30 行，标题 ≤60 字符
- 「期望的答案长什么样」强制必填——它决定外网侧能否直接交付而不是猜

## 6. CLI 面

```
outbox.py new --type T [--project X] [--block Y]   # 生成预填占位草稿，打印绝对路径
outbox.py commit <draft>                           # 两道机 → 分配 ID/占位化/归位/重建清单
outbox.py list [--status S] [--type T]
outbox.py audit                                    # 携出前体检
outbox.py sync-inbox                               # 回执写回，由脚本改文件
outbox.py bundle [--out PATH]                      # git commit + git bundle create
outbox.py answer <ID> --status S [--note "..."]     # 外网侧生成 inbox/<ID>.md
outbox.py selftest                                 # 内置用例，装完先跑
```

模型的正常路径只有三步：`new` → `edit` 逐个替换占位符 → `commit`。被拒就按行号 `edit` 修再 `commit`，自纠。

Windows 硬要求：显式 `encoding="utf-8"` 读写，`sys.stdout.reconfigure(encoding="utf-8")`，状态标记只用 ASCII（`[ok]` `[reject]` `[warn]`），不用 emoji。

## 7. 两道脱敏机

**第一道（复用 arcadia-1）** — `sanitize_bridge.py` 按 `_local/config.yml` 或环境变量定位 `analog-agents/tools/sanitize_snapshot.py`，import 其 `load_token_map` + `sanitize_text`，套现有 `_local/sanitize-map.yml` 再叠 `_local/outbox-map.yml`。找不到就打 `[warn]` 并降级为纯内置规则，不崩。缺 `yaml` 模块时 map 降级为 `key=value` 行解析。

**第二道（新增）** — `guard.py` 结构检测，命中即拒绝定稿：

| 规则 | 拦什么 | 处置 |
|---|---|---|
| R0 | `<...>` 占位符未替换 | reject |
| R1 | model card 体、`subckt` 定义体、`library`/`section`/`endsection` 块 | reject |
| R2 | 真实 `include`/`.include`/`ahdl_include` 路径（非 `/path/to/...` 形式） | reject |
| R3 | `techfile` `.oa` `.lib` `liberty` `diva` `assura` `calibre` `drc` `lvs` `antenna` `layermap` `rule deck` `cdl` | reject |
| R4 | `Library name:` `Cell name:` `libId` `cellView` 带非占位值 | reject |
| R5 | 绝对路径与用户名：`X:\` `/home/` `/opt/` `/eda/` `/Users/` UNC `\\host\share` | reject |
| R6 | 不在 `own-cells.txt` 白名单的 master 名 | **自动替换**为 `<cell_NNN>`，追加 `_local/cell-map.yml` |
| W1 | 正文超 200 行 / 证据超 30 行 / 缺 `related_wiki` | warn 不拦 |

R6 用替换而非拒绝，避免打断流程；映射跨记录稳定（首见顺序编号）。记录另给非敏感字段 `class:`（如 `lv-nmos`），让外网侧在没有真名时仍能推理。

## 8. SKILL.md 为 27B 定的约束

- frontmatter **只写 `name` + `description`**，一个多余字段都不加（见 §3 的忽略／抛错清单）
- `description` ≤500 字符，内嵌 `TRIGGER on:` 触发词表，照 arcadia-1 同级技能的折叠写法
- 正文 ≤110 行，全祈使句、编号步骤、无分支散文；细节推给 `references/`
- 启动打印 `[outbox-recorder] effort: not-gated`（照 analog-learn 的显式退出，同时满足 effort-contract 的启动打印规矩）
- 三条硬禁写在正文顶部：① 禁调 `web_search`/`web_fetch`；② 禁改既有记录、禁自算 ID、禁自写 MANIFEST/index；③ 禁为记录里的问题当场动手修

## 9. 与 arcadia-1 其他技能的关系

| 技能 | 关系 |
|---|---|
| analog-wiki | 只读引用 `corner-`/`anti-` ID 填 `related_wiki`，绝不写回 |
| analog-evolve | 产物互不相交：evolve 提炼设计知识进内网 wiki，outbox 记工具链诉求给人携出 |
| analog-learn | 无交集（它只写 `learn/`） |
| analog-netlist-crawl | 证据可引 `output/netlist-crawl/<dut>/<dut>_interpretation.md`，引用同样过两道机 |

arcadia-1 的 hooks 只对 `.scs|.sp|.net` 写入与 `spectre|virtuoso-bridge` 触发，**本技能写 .md 不被任何 hook 校验**，正确性只能靠 `commit` 里的 guard。

## 10. 查重（skills-check-before-create 路径 A）

门禁口径偏离并已交代：G3/G4 查重跑在**目标库**（arcadia-1 八个仓 + `skills/local/` 33 个技能），G2 配额不适用（本技能不 junction 进 `~/.qoder-cn/skills`，不吃 Qoder 每轮注入预算）。

结论：全 analog-agents 树 grep `internet|airgap|offline|outside` **零命中**。analog-learn 只写 `learn/`；analog-wiki 只写 `wiki/` 的 6 类固定条目且 effort=lite 时禁写；analog-evolve 从 `iteration-log.yml` 提炼进同一个内网 wiki。三者产物全在内网内部消费，**没有一个面向「人携出外网」**。缺口真实，可建。

## 11. 验证计划

- **G6 格式校验**：`name` 匹配正则、`description` ≤500 字符、`SKILL.md` ≤500 行、不含被忽略字段与驼峰别名、frontmatter 以整行 `---` 开合。用 DSH 自己的解析器跑，不用自制校验器。
- **G7-a DSH 侧机制**：本机 `~/.dsh/skills` 是符号链接指向 MySkills，而 `MySkills/DSH improve/outbox-recorder/SKILL.md` 距根 3 段、超出「最深 2 段」的发现范围，所以本机 DSH 不会自动看到它（不污染）。验证方式是另建临时发现根，或直接 import `dsh-skill-filesystem/lib/index.js` 的解析函数跑真实加载路径。
- **G7-b 脚本侧机制**：`new`→`edit`→`commit` 三步跑通；guard 拦住故意塞入的 model card、真实路径、未替换占位符；`audit`/`sync-inbox`/`bundle`/`selftest` 全绿。
- **G7-c 27B 可执行性**：用 ModelScope api-inference 上的 `Qwen/Qwen3.8-27B` 作被测模型，搭一个最小 agent loop（DSH 形状的小写工具名）跑真实任务，看它能否无帮助走完三步协议。**若连不上或限流/流量耗尽则按用户指示跳过**，并在证据里写明跳过原因，不算验证通过。
- 证据落 `skills-check-before-create/reports/adoption-outbox-recorder.md` 并入 git。

**明确验不到的部分**：本机 DSH 挂的是外网大模型，代表不了内网 27B 的实际执行率；G7-c 用的是云端同名模型，也不等于内网本地部署那一份。「弱模型可执行性」最终只能靠设计约束（短正文、结构化工作全压进脚本、三步协议、被拒自纠）保证，真实命中率要用户内网首跑才知道。
