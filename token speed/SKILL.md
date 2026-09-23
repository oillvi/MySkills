---
name: token-speed
description: Use at the end of every assistant turn in a Qoder session, or when the user asks about token speed, TPS, tok/s, output rate, cache hit rate, or token usage (M) of the current turn. Reads local Qoder session logs.
---

# token-speed：回合末 token 速度一行

## 概述

每轮回复末尾追加一行本回合真实 token 统计（TPS 为主指标）。数据只读自本机 Qoder 会话日志；脚本纯标准库，单文件。

## 每轮动作（按顺序）

1. 回复正文定稿后运行：`python ~/.qoder-cn/skills/token-speed/tokspeed.py`
2. 把 stdout **原样**贴成独立一行，不改数字、不合并进段落。
3. 位置固定：【总结】之后、`技能：` 尾行之前。四段式与 caveman 规则不受影响。
4. 脚本报错或 10 秒无输出：本轮跳过尾行，不手工编数字。

## 口径（数字含义）

- 窗口 = 当前主会话回合起点之后 started 的**全部已完成**请求；正在生成的末条回复不计入（行尾 `末条回复不计` 即此意）。
- 子智能体请求**计入**（用户裁定 2026-09-23）：含 `turn_id == session_id` 的后台回合；`models:` 段按 `request.started` 的 `data.model` 短名（`/` 后半段）给各模型次数。
- `无 token 上报` ≠ 0：通道不落 usage 时只给耗时，绝不能把 0 当真实速度。
- tok/s = Σoutput_tokens ÷ Σ耗时（仅计有 usage 的请求）；cache = Σcache_read_input_tokens ÷ Σinput_tokens；M = (Σinput_tokens + Σcache_creation_input_tokens + Σoutput_tokens) ÷ 1e6。

## 数据源与实现

- 事件日志 `~/.qoder-cn/logs/sessions/<项目>/<会话>/segments/<run>.jsonl`：耗时（model.request.started → model.response.completed）与回合（turn_id）。
- 会话 `~/.qoder-cn/projects/<项目>/<会话>.jsonl`：`message.usage`，**request_id 在 usage 对象内部**。
- 多会话并发时用命令锚定选 segment：近 5 分钟活跃的 segment 里挑「shell 命令文本含 `tokspeed.py`」的那条 = 调用方自己（mtime 最新可能被并行会话抢走，实测过）。
- 脚本 `tokspeed.py`（本目录）；31 条单测在 `tests/`。改脚本后跑 `python -m unittest discover -s tests -t .`，全绿才算完。
- 环境变量 `QODER_CN_HOME` 可重定向日志根（默认 `~/.qoder-cn`），测试用。

## 常见错误

- 把 `无 token 上报` 读成速度为 0：那是通道没上报，耗时列仍然真实。
- 想把末条回复的 token 算进去：做不到，它在统计之后才生成。
- 手工估算 token 数：禁止。一律以脚本 stdout 为准。
