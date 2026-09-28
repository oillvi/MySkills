# 记录 schema

`outbox.py` 生成的记录都是「YAML frontmatter + Markdown 正文」。这份文件是逐字段的定义与完整示例。模型按需 `read`，不会被自动加载。

## frontmatter 字段

| 字段 | 谁写 | 说明 |
|---|---|---|
| `id` | 脚本 | `commit` 时分配，形如 `prob-0007`。草稿阶段是 `null` |
| `type` | 脚本 | `new --type` 决定，六种之一 |
| `status` | 脚本 | 草稿 `draft`；定稿 `pending-review`；回执后 `approved` / `rejected` / `answered` / `wontfix` |
| `created` | 脚本 | `new` 那天，不是 `commit` 那天——记录的是问题被观察到的时间 |
| `project` | 脚本 | 取 `_local/config.yml` 的 `project`，或 `new --project` |
| `block` | 脚本 | `new --block`，可空 |
| `severity` | **模型** | `blocking`（干不下去）/ `slowing`（能绕但代价大）/ `annoyance` |
| `effort_seen` | 脚本 | 取 config 的 `effort_seen`，缺省 `standard` |
| `class` | 模型（可选） | 器件类别的非敏感标签，如 `lv-nmos` / `poly-res` / `mim-cap`。真名被占位化之后，外网侧靠这一栏知道在讲什么器件 |
| `related_wiki` | 模型（可选） | arcadia-1 wiki 的 ID 列表，只接受 `topo-` `strat-` `corner-` `anti-` `proj-` `case-` 开头的。**只读引用，不写回 wiki** |
| `derived_from` | 脚本／模型 | `skill-proposal` 必填。模型只要把 ID 写进「派生自」那一节，`commit` 会自动同步到这里 |
| `recurrences` | 脚本 | 同类提案再次出现时由脚本 +1，模型不碰 |
| `env` | 脚本 | `harness` / `desktop` / `arcadia1_sha` / `model`，全取 config，缺省 `unknown` |

## ID 前缀

| 类型 | 前缀 | 例 |
|---|---|---|
| `problem` | `prob-` | `prob-0007` |
| `wish` | `wish-` | `wish-0002` |
| `bottleneck` | `bneck-` | `bneck-0001` |
| `need-outside` | `need-` | `need-0004` |
| `drift` | `drift-` | `drift-0003` |
| `skill-proposal` | `prop-` | `prop-0001` |

四位补零。号码由脚本扫 `records/` 里同前缀的最大号 +1 得出，**没有计数器文件**，所以删记录不会导致重号。

## 文件名与落点

```
records/<type>/<YYYYMMDD_HHMMSS>__<id>__<slug>.md
```

命名照 arcadia-1 `AGENTS.md` 的规矩：**段内单 `_`，段间双 `__`**。所以日期时间里的 `_` 是段内分隔，三段的边界一定是 `__`，可以无歧义地切开。

`slug` 由标题里的 ASCII 字母数字生成，截到 40 字符。纯中文标题会得到 `note`，这是有意的兜底，不是 bug。

## 各类型的必填节

`commit` 会检查这些节存在且不为空、也不能是 `无`：

| 类型 | 必填节 |
|---|---|
| `problem` | 现象 / 已试过 / 期望的答案长什么样 |
| `wish` | 想要的能力 / 为什么现在做不到 / 期望的答案长什么样 |
| `bottleneck` | 现象 / 当前代价 / 期望的答案长什么样 |
| `need-outside` | 要找什么 / 用途 / 期望的形式 |
| `drift` | 跑飞的表现 / 触发点 / 期望的约束 |
| `skill-proposal` | 派生自 / 观察到的重复动作 / 为什么现在做不到 / 期望能力一句话 / 建议落点 |

其余节标了「可选」，没有内容就写 `无`，或者按模板提示整节删掉。

**「期望的答案长什么样」是整套设计里最重要的一栏。** 内网侧只描述现象，外网侧要靠这一栏知道该交付什么。写「帮我看看」等于没写；写「`simOutputFormat` 该设成什么，以及为什么第三个 corner 会 differs」才能直接办。

## 完整示例（定稿后的样子）

```markdown
---
id: prob-0007
type: problem
status: pending-review
created: 2026-09-28
project: ldo-tapeout
block: comparator
severity: blocking
effort_seen: standard
class: lv-nmos
related_wiki: [anti-003]
derived_from: []
recurrences: 0
env:
  harness: 0.1.7-rc.2
  desktop: 2.0.15
  arcadia1_sha: 4f2c9a1
  model: qwen3.8-max-27B
---

# Corner sweep stops after the third corner

## 现象
ADE XL 在第三个 corner 之后停下，打印 `cannot open raw file`。
剩下四个 corner 一次都没跑。

## 已试过
- 重启仿真，仍然停在 corner 3
- 清掉结果目录重跑，仍然停在 corner 3
- 把 corner 顺序调换，改成停在新的第三个

## 期望的答案长什么样
两点：一是哪个设置能让剩下的 corner 继续跑；二是为什么总是第三个
停，是不是结果目录的命名与并发写入冲突。

## 证据
```
M1 (out in vss vss) <cell_001> w=2u l=0.18u m=2 nf=2
R1 (out fb) <cell_002> r=10k
```

## 改进方向
无
```

注意示例里 `<cell_001>` `<cell_002>`：原文写的是 PDK 的 master 名，`commit` 时第一道机与 R6 把它们换掉了，同时把对应关系追加进 `_local/cell-map.yml`。模型不需要也不应该自己去做这个替换。

## 回执

外网侧用同一个脚本产回执：

```
python scripts/outbox.py answer prob-0007 --status answered --note "设 simOutputFormat=psfxl"
```

生成 `inbox/prob-0007.md`。人把它带回内网，跑 `sync-inbox`，脚本会：改 `status`、在记录末尾追加一节 `## 外网回执`、把回执文件移进 `inbox/_done/`、重建 `MANIFEST.md` 与 `index.jsonl`。

模型不参与回执合并。**已定稿记录的任何修改都由脚本做。**
