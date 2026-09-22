# 绿测报告（技能生效后的行为 × 三轮）

**条件**：技能 junction 至 `~/.qoder-cn/skills/smart-subagent`（SKILL.md 版本 v1 → v1.1 → v3）；其余同基线（独立 CLI 会话、`--permission-mode auto`、同 prompt 族）。
**判据**：分派是否发生（看 `<sessionId>/subagents/`）、派谁、模型钉桩、技能是否被调用（看会话尾行「技能：…」）。

## 三轮矩阵

| 轮 | 会话 | 任务 | 技能调用 | 分派 | 评价 |
|---|---|---|---|---|---|
| 1 | green-S1…S5（v1 描述） | 5 个小场景 | 全部「未调用」 | S3 派 Explore；其余 0 | 与基线一致——**测试设计复盘：5 个小任务按技能自身经济学本就不该派** |
| 1′ | canary×2 | 可见性探测 | — | — | 技能可见（能背出 description）；agent 类型可见（glm-scout/ds-coder 在列） |
| 2 | H1（重勘察，v1.1） | 目录摸底+风险归纳 | 未调用 | **派 Explore**（内置，非 glm-scout） | 分派发生但**选错 agent**（贵模型）；报告质量高、含 file:line 与风险归纳 |
| 2 | H2（批量执行，v1.1） | 写 3 脚本并跑通 | 未调用 | 0 | 主线程自写（Read×1 Write×3 Bash×5），输出正确 |
| 2 | H3（+「用便宜模型跑个腿」，v1.1） | 列 model/tools 字段 | 未调用 | **派 glm-scout ✓** | **主线程仅 1 次 Agent 调用**；子代理 7/7 行 GLM-5.3-Flash、工具 Glob×1+Read×2；答案正确 |
| 2 | S1r | mklink 搜索 | 未调用 | 0 | 小任务，同基线 |
| 3 | P1–P4（=H3 题面**去掉**关键词，v3 描述） | 列 model/tools 字段 | 全部「未调用」 | **0/4** | 纯 description 不驱动分派 |
| 3 | **PX（「使用 smart-subagent 技能」）** | 列 model/tools 字段 | **技能：smart-subagent ✓** | **派 glm-scout + 主线程抽验 ✓** | **全链路达标**：决策 → 分派 → 验收（「坐标验证通过」「已抽验核实」）→ 汇报 |
| 3 | H2r（v3） | 写 3 脚本并跑通 | 未调用 | 0 | 执行类仍未自分派 |

## 关键结论

1. **技能内容有效**：一旦被调用（PX），行为完全按设计走——决策表 → 分派 glm-scout → 主线程抽验 → 按格式汇报。
2. **显式路径全部工作**：`使用 smart-subagent 技能` 或 `用便宜模型` 类措辞 = 实测 2/2 触发（PX、H3）。
3. **自主调用未达成**：三轮共 13 个机会会话里只有 PX 正式调用了技能；description 从 v1（Use when）改到 v3（命令式+中文）均未扳动 P1–P4（0/4）。属模型对 skill 调用决策的机制性限制，已如实记录。
4. **执行类块仍倾向自己干**（H2/H2r 2/2 未分派）；勘察类在有显式信号时可派（H3/PX），但 H1 会选内置 Explore 而非便宜的 glm-scout。
5. **分派正确时模型钉桩 100% 生效**（glm-scout = GLM-5.3-Flash，7/7 assistant 行）。

## 建议用法（现状，写进 README）

- 期望可靠触发：说「用便宜模型」「派子智能体」「使用 smart-subagent」。
- 重勘察任务：可能被自动派，但默认选内置 Explore——要点名 `glm-scout` 才省钱。
- 执行类：目前建议在提示里点名 `ds-coder`。

## 未闭环项（诚实清单）

- description 自主触发率 0/4（P1–P4），v1→v3 两轮修改均未生效；未做 5× 措辞微测（预算取舍）。
- H1 选 Explore 而非 glm-scout： 「重勘察优先便宜 agent」这一条未稳住。
- 执行类 2/2 未分派。