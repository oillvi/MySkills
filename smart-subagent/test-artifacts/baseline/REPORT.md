# 基线红测报告（红：技能安装前）

**条件**：smart-subagent 技能未安装；glm-scout / ds-coder 已注册（`agents list` = 7）；每场景一个独立 CLI 会话（`qoderclicn -p --permission-mode auto -w "E:\Work\Qoder Projects\MySkills"`），prompt 自包含。
**证据**：本目录 `*.log`（会话输出）+ `~/.qoder-cn/projects/E--Work-Qoder-Projects-MySkills/<sessionId>.jsonl`（工具/模型/轮数）；各会话 `<sessionId>/subagents/` 目录**全空**（无任何子智能体 transcript）。

## 结果矩阵（5/5 零分派）

| # | 场景 → 期望 | 实际行为 | 工具调用 | 分派 | 会话 ID |
|---|---|---|---|---|---|
| S1 | 勘察：找 mklink 全部引用 → 派 glm-scout | 主线程自己干，答案正确（4/4 命中） | Grep×1 | ❌ | 29164a6a |
| S2 | 执行：修 bug 并跑通 → 派 ds-coder | 主线程自己干，修复 + 运行验证通过 | Read×1 Edit×1 Bash×1 | ❌ | 7c3a3022 |
| S3 | 设计：zip 工具方案 → 不外包 | 主线程自己做；自动触发 `brainstorming` 技能 | Read×2 Bash×2 Skill×1 | ❌ | ef98860c |
| S4 | 小活：draft→final → 不外包 | 主线程自己干，改对 | Read×1 Edit×1 | ❌ | d9dda477 |
| S5 | 链路：统计行数写文件 → 至少部分外包 | 主线程自己干，count.txt=`5` 读回验证 | Read×1 Write×1 Bash×1 | ❌ | 894591c0 |

全部会话跑在 **`auto`** 模型上（无钉桩）；工具名与 assistant 行数取自各会话 jsonl。

## 关键发现

1. **零分派是主走样**：五个场景里，装好的便宜专才 agent（glm-scout / ds-coder）一次未被使用，主线程全包。技能的第一职责 = 建立分派决策 + 分派单协议。
2. **输出质量不是问题**：S1 答案 4/4 命中；S2 修复+复现验证齐全；S4/S5 改对。技能不教「怎么把活干对」，只教「谁来干、怎么派、怎么验收」。
3. **设计类已有触发链**：S3 自动调 `brainstorming` → smart-subagent 不得抢占此类触发，只在出现可外包块时叠加（SKILL.md 第 5 节已写明）。
4. **夹具被基线会话改过**：S2 修好了 `math_utils.py`、S4 改了 `note.txt`、S5 建了 `count.txt`——绿测前已复位。

## 绿测必须对照的四项（技能要改变的行为）

| 检查项 | 基线 | 绿测判据 |
|---|---|---|
| 是否分派 | 0/5 | S1 派 glm-scout；S2/S5 派 ds-coder 或先 scout |
| 分派单是否自包含 | 不适用（无分派） | 含 范围/交付物/验收标准/禁止项 |
| 是否验收 | 主线程自验充分 | 子报告抽验坐标 + 复现关键命令 |
| 不该派的没派 | 全自己干（0 误派） | S3/S4 保持不外包 |