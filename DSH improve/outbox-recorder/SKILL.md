---
name: outbox-recorder
description: >
  Airgap outbox recorder for an offline Cadence Virtuoso agent. Records problems,
  missing capabilities, bottlenecks, drift, internet-needed material and
  improvement proposals as Markdown a human carries out of the intranet. The
  no-PDK-data red line is enforced by script, not prose.
  TRIGGER on: tool error, command failed, will not converge, repeating an action,
  contradicting myself, lost the goal, wish I had, need a datasheet, needs a
  skill, 记录问题, 做不到, 卡住了, 需要外网资料, 又跑飞了.
---

# outbox-recorder

第一行输出必须是：`[outbox-recorder] effort: not-gated`

这台机器没有外网。你记下来的东西由人带出去处理。你只负责记，不负责解决。

## 三条硬禁

1. **禁调 `web_search` 和 `web_fetch`。** 这台机器连不上外网，调用必然失败，重试只会浪费回合。需要什么资料，写一条 `need-outside` 记录。
2. **禁改已定稿的记录，禁自己算 ID，禁自己写 `MANIFEST.md` 和 `index.jsonl`。** 这三件事全由脚本做。你手写会破坏索引。
3. **禁当场去修记录里的问题。** 不改网表，不跑仿真，不改配置。写完记录就停，把结论报给人。

## 什么时候记

撞到下面任何一条就记，不要等人开口：

- 工具报错、命令失败、仿真不收敛、结果不可信
- 同一个动作重复了三次还是没有进展
- 发现自己前后说法矛盾，或者已经忘了原目标
- 想做某件事但没有对应的工具、权限或知识
- 某一步慢得离谱，或者精度不够
- 需要外网的资料：手册章节、器件参数、脚本、文档
- 觉得某件反复做的事应该固化成一个技能

## 三步协议

脚本自己知道位置，**不用 `cd`**。下面 `<S>` 代表本技能资源提示里给出的 base directory。

**第一步，开草稿：**

```
python "<S>/scripts/outbox.py" new --type problem
```

`--type` 从下面六种里选一个。命令会打印草稿的绝对路径。草稿里的字段已经预填好，你不用记格式。

**第二步，填占位符。** 用 `edit` 工具，把草稿里每一个 `{{...}}` 换成真实内容。一次换一个，锚点就是那串 `{{...}}` 本身。规则：

- 标题写在 `# ` 那一行，不超过 60 字
- `severity` 三选一：`blocking`（干不下去）、`slowing`（能绕但代价大）、`annoyance`
- 「期望的答案长什么样」必须写具体。写清楚外网那边要交付什么：一段说明、一个脚本、一份手册页、还是一个器件参数。这一栏写含糊，整条记录就白记了
- 可选项没有内容就写 `无`；标了「把整节删掉」的就整节删掉
- **一个 `{{...}}` 都不许留**，留着会被拒

**第三步，定稿：**

```
python "<S>/scripts/outbox.py" commit "<草稿路径>"
```

看到 `[ok] committed` 就成功了。把记录 ID 报给人，然后停。

**被拒怎么办：** 输出里每条拒绝都带 `文件:行号 规则号`。按行号用 `edit` 改那一行，再跑一次 `commit`。草稿不会被删，可以反复改。**不要**改用 `write` 重写整个文件，也**不要**绕过脚本手工把文件挪进 `records/`。

## 六种类型

| `--type` | 记什么 |
|---|---|
| `problem` | 撞到的具体问题：报错、卡死、结果不可信 |
| `wish` | 想要但当前没有的能力或工具 |
| `bottleneck` | 效率或精度瓶颈，要给出数字 |
| `need-outside` | 要从外网拿的东西，写到能直接去搜的程度 |
| `drift` | 自己跑飞了：重复动作、自相矛盾、丢了目标 |
| `skill-proposal` | 提议的改进方向，供人裁决是否建技能 |

`skill-proposal` 有一条额外规矩：「派生自」那一节必须写一条**已经存在**的 `prob-` 或 `drift-` 记录 ID。不许凭空提议。所以顺序永远是先记 `problem` 或 `drift`，再记 `skill-proposal`。脚本会自己去 `records/` 核这个 ID 存不存在。

## 红线

**严禁写进记录的东西**（脚本会拦，但你自己先避开，省一轮）：

- PDK 的 model card、器件模型参数、tech file、DRC/LVS 规则文件
- 库名、单元名、视图名，以及 `Library name:` / `Cell name:` 这类抬头
- 真实绝对路径、用户名、服务器名、共享目录

**允许写的**：本项目自己的网表片段，最多 30 行，放在代码围栏里。里面的 PDK 单元名会被脚本自动换成 `<cell_001>` 这样的占位符，你不用管，也不要自己去改它。

提到工具名和检查名是允许的，比如「Calibre DRC 跑了 12 条违例」——这是在描述问题，不是泄露数据。脚本对这类词只告警不拦。

描述路径时用 `<project>/tools/xxx.py` 这种占位写法。

## 与其他技能的关系

| 技能 | 关系 |
|---|---|
| `analog-wiki` | 只读引用它的 `corner-` / `anti-` ID 填进 `related_wiki`，**绝不写回** wiki |
| `analog-evolve` | 互不写对方的产物。它提炼设计知识进内网 wiki，你记工具链诉求给人带出去 |
| `analog-learn` | 无交集 |
| `analog-netlist-crawl` | 证据可以引它的解读文件，引用同样要过红线 |

arcadia-1 的 hooks 只盯网表和仿真产物，**不会校验你写的 Markdown**。所以正确性全靠 `commit` 里的两道门禁，没有别的兜底。

## 细节在哪

需要更多信息时用 `read` 读，不要猜：

- `references/record-schema.md` — 六种类型逐字段的定义与完整示例
- `references/guard-rules.md` — 每条拦截规则的原文、为什么、怎么改才过
- `references/install.md` — 给人看的：安装、配置、携出、回执
