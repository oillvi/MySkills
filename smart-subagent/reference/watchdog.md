# 看守探针（Watchdog Probe）方案与流程

给「派出去的子任务」加一层外部看守：主线程用极轻量探针周期性确认子智能体没卡死/绕圈，异常时安全终止、归因、重派。设计依据：OpenHands Stuck Detector 五模式、LoopBuster 分级断路器（FuzzyRepeat 近似指纹）、各框架预算数字（LangGraph/crewAI/SWE-agent）、本机抓手（transcript 实时落盘 + TaskStop）。先例调研见记忆 `subagent-watchdog-prior-art`。

## 0. 组件一览

| 组件 | 落点 | 职责 |
|---|---|---|
| 探针卡 | 分派单第五件（§1） | 定预算：步数/时限/里程碑/已知坑/检查点 |
| 探针脚本 | `tools/probe.py`（v0 已落地） | 只读 transcript 尾部，输出 ≤10 行 digest；`--fine` 按类别跑细探针（§3.1） |
| 判据表 | 本文件 §2 | 判定 正常 / 可疑(WARN) / 卡死(BLOCK) |
| 处置协议 | 本文件 §3 | WARN=加细探针；BLOCK=TaskStop+归因+重派 |

## 1. 流程（一次带看守的派单）

1. **派单**：分派单四件套之外加第五件「探针卡」：

```text
探针卡：
- 预算：≤N 步 / ≤M 分钟；里程碑：X 完成时应看到 <现象>
- 已知坑：<上次重派的教训，没有写「无」>
- 检查点：中间产物落 <路径>（中断后续接用）
```

2. **后台派单**：`Agent(run_in_background=true)`；记下 task-id / agent 名。
3. **巡检**：主线程每 ~60s 跑 `python tools/probe.py <transcript 路径> --budget N`，拿 ≤10 行 digest（事件计数、最近 5 步工具序列、近似重复指纹、停滞秒数、里程碑是否出现）。
4. **判读**：高级模型按 §2 表给结论：正常 / 可疑 / 卡死——剩余判断按当时情况人工定夺。
5. **处置**：按 §3；探针本身可按 digest 回传临时重设计（换指标/加细度），但守 §4 红线。
6. **完成**：回到验收协议（抽验坐标 + 复现命令）。

## 2. 判据表（默认阈值，可被探针卡覆盖）

| 信号 | WARN（可疑） | BLOCK（卡死） | 依据 |
|---|---|---|---|
| 同工具+同参数全等重复 | 2 次 | 3 次 | OpenHands Action-Observation 4+（本地收紧） |
| 近似重复指纹（编辑距离/Jaccard） | 3 次 | 5 次 | LoopBuster FuzzyRepeat；防「微变循环」（dsh 帖教训） |
| A-B-A-B 交替振荡 | 3 轮 | 6 轮 | OpenHands Alternating 6+ |
| 连续报错不收敛 | 2 次 | 3 次 | OpenHands Action-Error 3+ |
| 连续独白无工具产出 | 2 条 | 3 条 | OpenHands Monologue 3+ |
| 事件停滞（无新事件） | 90s | 300s | cron 监控实践 300s |
| 步数 / 时限 | 预算 80% | 预算 100% | LangGraph/crewAI(25)/SWE-agent 预算类；默认 ≤20 步 / ≤10 分钟 |

判定只看**最近事件窗口**（20 条），按语义/指纹比较而非对象全等（OpenHands 做法）。

## 3. 处置：WARN / BLOCK（分级断路器）

- **WARN**：不打断子任务；按 §3.1 细探针模板取对应类别一张（coder/scout）定点细查；模板不覆盖时才临场设计临时探针（例：盯关键输出文件 mtime）。连环 2 次 WARN 升级 BLOCK。
- **BLOCK**：① `TaskStop(<task_id>)` 安全终止；② 读已落盘 transcript + 中间产物归因（鬼打墙/弯路/卡死/坏指令——区分「预算耗尽」与「异常」）；③ 把坑写进新探针卡「已知坑」；④ 从检查点重派；⑤ 同一任务 BLOCK ≥2 次 → 停下上报用户，不再自动重派。

## 3.1 细探针模板（WARN 后定点细查，2026-09-23 落地）

粗筛（probe.py 默认 5 模式）报 WARN 后，按任务类别取下面一张卡换细探针，不再临场发挥。命令与 `tools/probe.py --fine` 的判据一一对应；阈值风格同 §2：普通数字=WARN，更大数字=BLOCK。

**细探针卡 · coder**（施工类：改文件 / 写脚本 / 修 bug）

```text
python tools/probe.py <transcript> --fine coder --expect "<验收命令子串>" --expect-file <交付物路径> --window 40
```

| 判据 | WARN | BLOCK | 抓什么 |
|---|---|---|---|
| C1 同路径反复改动（Write/Edit/NotebookEdit） | 同一路径 3 次 | 5 次 | 改了又改的鬼打墙 |
| C2 验收命令缺席（--expect 子串在 Bash 里 0 命中） | 0 命中即 WARN | — | 干完活从不验证 |
| C3 交付物缺位（--expect-file 从未被写且磁盘无此文件） | 缺位即 WARN | — | 里程碑产物没影 |

**细探针卡 · scout**（勘察类：定位 / 清点 / 追引用）

```text
python tools/probe.py <transcript> --fine scout --window 40
```

| 判据 | WARN | BLOCK | 抓什么 |
|---|---|---|---|
| S1 查询重复（Grep/Glob 同查询规范化计数） | 3 次 | 5 次 | 同一条搜索反复跑 |
| S2 路径新鲜度（最近 5 逻辑轮 ≥3 次 Read 全是旧路径） | 命中即 WARN | — | 没有新坐标产出 |
| S3 同文件重读 | 同一路径 3 次 | 5 次 | 读了又读不推进 |

- fine 行计入 digest 的 ≤10 行总量；fine 命中抬高 exit code（WARN 级=1、BLOCK 级=2）；不加 `--fine` 时输出与 v0 完全一致。
- 任务对错不在这一层判：`--expect` 只查「验收命令**有没有被执行**」（子串来自分派单四件套的「验收标准」）；结果对不对回验收协议（重跑命令）定。「结束时测试仍红」是验收协议第 2 步自然会暴露的事，不归探针。

## 4. 体量红线（探针不许反噬）

- `probe.py` 单文件、只读、纯标准库；单次 <2s；输出 ≤10 行结构化 digest，不搬原文。
- 巡检 60s 一次（探针卡可调 30–120s）；无变化只回 1 行「静默」。
- 临时探针同样守此红线；探针开销总账要远小于它救回的浪费。

## 5. 检查点与恢复（LangGraph checkpoint 的本机版）

- 分派单要求子任务把中间产物落盘到指定路径（进度文件/半成品），即检查点。
- BLOCK 重派时明写「从 <路径> 续接，不要重做」。

## 6. 与现有机制接线

- 分派单配方（SKILL.md §2）追加第五件「探针卡」（下一轮改 SKILL.md）。
- 花名册照旧约束「派谁」，看守不改变派单对象（2026-09-23 起子任务默认 `mimo-worker` = mimo-v2.6-flash）。
- probe digest 与处置记录留本地存档（不入库）。

## 7. 实施清单

1. ~~通路金丝雀~~ **已完成（2026-09-23）**：mimo-v2.6-flash 子智能体通道金丝雀过（钉 21fa3498 key，transcript 实证）。
2. ~~`tools/probe.py` v0~~ **已完成（2026-09-23）**：工具已落盘 `tools/probe.py` + `tools/test_probe.py`，9 单测绿（`--budget/--window`；单测喂伪造 transcript 断言五模式命中）。
3. ~~红绿行为测试~~ **已完成（2026-09-23）**：红=无看守绕圈无人管；绿=探针抓 BLOCK + TaskStop + 检查点重派成功（报告在本地归档 MySkills-archive，未随仓库分发）。
4. ~~SKILL.md 接线~~ **已完成（2026-09-23）**：§2 +探针卡行、§4 +看守处置权归主线程；README FAQ 同步。
5. ~~细探针模板~~ **已完成（2026-09-23）**：§3.1 两张卡（C1-C3 / S1-S3）+ `probe.py --fine coder|scout`，单测新增 ≥6 例。
6. [缓做] 类别默认预算进探针卡配方（步数/时限双上限，对齐 crewAI 25 / 腾讯 8 步口径）——用户 2026-09-23 拍板先放着，等实测觉得预算难填再上。