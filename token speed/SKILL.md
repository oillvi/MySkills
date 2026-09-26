---
name: token-speed
description: Use at the end of every assistant turn in a Qoder session, or when the user asks about token speed, TPS, tok/s, output rate, cache hit rate, or token usage (M) of the current turn. Reads local Qoder session logs.
---

# token-speed：回合末 token 速度一行

## 概述

每轮回复末尾追加本回合真实 token 统计（TPS 为主指标）：主会话一行，用了子智能体时每个子模型各一行。数据只读自本机 Qoder 会话日志；脚本纯标准库，单文件。

## 每轮动作（按顺序）

1. 回复正文定稿后运行：`python ~/.qoder-cn/skills/token-speed/tokspeed.py`
2. 把 stdout **原样**贴成末尾若干行（本回合有子智能体时就是多行），不改数字、不合并进段落、不重排顺序。
3. 位置固定：【总结】之后、`技能：` 尾行之前。四段式与 caveman 规则不受影响。
4. 脚本报错或 10 秒无输出：本轮跳过尾行，不手工编数字。

## 口径（数字含义）

- 窗口 = 当前主会话回合起点之后 started 的**全部已完成**请求；正在生成的末条回复天然不计（它产生于统计之后，自 2026-09-26 起不再在行尾提示）。
- **主会话与子智能体分开、分行统计**（用户裁定 2026-09-26）：主会话占第一行，之后**每个子智能体模型各占一行**，形如
  `tok/s: 主 125 req · 35.8 tok/s · out 125.0k · 3494.5s · cache 90.5% · 19.070M`
  `tok/s: 子 mimo-v2.6-flash×151 · 59.0 tok/s · out 153.2k · 2598.0s · cache 90.0% · 3.106M`
  主行的 tok/s / 耗时 / cache / 用量**只算主会话自己的请求**，子行只算 `turn_id == session_id` 且该模型的请求；没用子智能体时只出主行、不带「主」字。子行**没有合计行**——不同模型的混合速度没有意义。各子行按请求数降序、名字升序排。
- 主行不重复主模型速度：主行只有一个模型时不列 `models:`（那一行的数字就是它的速度）；主行多模型、或整行无上报（需要知道是哪个模型）时才列 `models:`。子行把模型名放在计数位（`子 <模型>×<n>`），所以子行不再出现 `models:`；事件里查不到模型名的请求归到 `未标注` 子行，不静默丢弃。
- 每行 tok/s = 该行自身 Σoutput ÷ Σ耗时（只算有 usage 的请求）；无上报的标 `无 token 上报`（行内部分无上报时附 `(k 无上报)`）、绝不显示 0。模型显示名过花名册：UUID 形态的 ref 换成别名（如 `4e190e86-…` → `deepseek-flash`），映射不到保持原文。子智能体请求的 usage 从 `subagents/agent-a*.jsonl` 转录按 request_id 取（父会话 jsonl 不含），所以子行也报真 TPS。
- `无 token 上报` ≠ 0：通道不落 usage 时只给耗时，绝不能把 0 当真实速度。
- tok/s = Σoutput_tokens ÷ Σ耗时（仅计该行有 usage 的请求）；cache = Σcache_read_input_tokens ÷ Σinput_tokens（**该行、本回合窗口内**的比值，不是整场任务累计）；M = (Σinput_tokens + Σcache_creation_input_tokens + Σoutput_tokens) ÷ 1e6。

## 数据源与实现

- 事件日志 `~/.qoder-cn/logs/sessions/<项目>/<会话>/segments/<run>.jsonl`：耗时（model.request.started → model.response.completed）与回合（turn_id）。
- 会话 `~/.qoder-cn/projects/<项目>/<会话>.jsonl`：`message.usage`，**request_id 在 usage 对象内部**。
- 子智能体转录 `~/.qoder-cn/projects/<项目>/<会话>/subagents/agent-a*.jsonl`：子智能体请求的 `message.usage` 只落这里（父会话 jsonl 不含），按 request_id 并进统计。
- 多会话并发时用命令锚定选 segment：近 5 分钟活跃的 segment 里挑「shell 命令文本含 `tokspeed.py`」的那条 = 调用方自己（mtime 最新可能被并行会话抢走，实测过）。
- 显示名映射：读 `~/.qoder-cn/skills/smart-subagent/roster.yml` 的 models 段 ref→别名（`TOKENSPEED_ROSTER` 可换文件）；文件缺失/解析失败退回原文，不阻断统计。
- 脚本 `tokspeed.py`（本目录）；66 条单测在 `tests/`。改脚本后跑 `python -m unittest discover -s tests -t .`，全绿才算完。
- 环境变量 `QODER_CN_HOME` 可重定向日志根（默认 `~/.qoder-cn`），测试用。

## 常见错误

- 把 `无 token 上报` 读成速度为 0：那是通道没上报，耗时列仍然真实。
- 把主行和子行的 tok/s 平均一下当「本回合速度」：模型不同、上下文规模不同，只能分行各读各的；要全量就把各行 out / 耗时 / M 相加后重算，别平均比值。
- 把 `cache 91.3%` 读成「整场任务的缓存命中率」：它是**本回合窗口内**该段请求的比值，回合越深、前缀越长数值越高。
- 想把末条回复的 token 算进去：做不到，它在统计之后才生成（这就是过去行尾那句提示的含义，现已不显示）。
- 手工估算 token 数：禁止。一律以脚本 stdout 为准。
