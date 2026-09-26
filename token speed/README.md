**English** | [简体中文](README.zh-CN.md)

# token-speed

Appends one line of **real token-speed stats** to the end of every assistant turn in a Qoder session: output TPS, duration, cache hit rate, token usage (M), and which models ran — computed from Qoder's local session logs, never estimated.

**简体中文：** 每轮回合末尾自动追加一行真实 token 速度统计（TPS / 耗时 / 缓存命中率 / 用量 M / 使用的模型），数据来自 Qoder 本地会话日志，不做估算。中文说明见 [README.zh-CN.md](README.zh-CN.md)。

## What it reports

Main session gets the first line; each subagent model gets a line of its own (user decision, 2026-09-26):

```
tok/s: 主 125 req · 35.8 tok/s · out 125.0k · 3494.5s · cache 90.5% · 19.070M
tok/s: 子 mimo-v2.6-flash×151 · 59.0 tok/s · out 153.2k · 2598.0s · cache 90.0% · 3.106M
```

Several subagent models → several 子 lines, sorted by request count (desc), then name. Without a subagent in the turn there is one line only, with no role label:

```
tok/s: 13 req · 39.0 tok/s · out 31.1k · 798.6s · cache 91.7% · 2.690M
```

- **tok/s** — total output tokens ÷ total duration, per line, over that line's requests with real usage only. Tokens and timing are paired by `request_id` between the event log (`model.request.started → model.response.completed`) and the session jsonl (`message.usage`)
- **主 / 子 lines** — the 主 line counts main-session requests only; each 子 line counts `turn_id == session_id` requests for that one model. Every field (`tok/s`, `out`, duration, `cache`, `M`) is per line. There is no blended 子 total: mixing speeds across models would be meaningless. Requests whose event carries no model name land in a `未标注` line instead of being dropped.
- **cache** — `cache_read_input_tokens / input_tokens`, per line, over this turn's window only (not the whole session/task)
- **M** — `(input + cache_creation + output) / 1e6`, per line
- **models** — the 主 line lists per-model rows only when the main session spanned several models or reported no usage at all (so you can tell which); a single main model is not repeated, since the line's number already is its speed. 子 lines carry the model name in the count position (`子 flash×151`), so they never print a `models:` section. Short name is the part after `/`; UUID-shaped names resolve to roster aliases (smart-subagent `roster.yml`), e.g. `4e190e86-…` → `deepseek-flash`; a model with no usage shows `无上报`, never a fake 0
- Channels that report no usage show `无 token 上报` ("no usage reported") with duration only — never a fake 0
- Window = all completed requests started after the current turn began; the in-flight final reply is never included (it postdates the measurement — since 2026-09-26 the line no longer spells that out)

## Install & run

Pure stdlib, read-only, single file:

```bash
python ~/.qoder-cn/skills/token-speed/tokspeed.py
```

`QODER_CN_HOME` overrides the log root (default `~/.qoder-cn`) for testing; `TOKENSPEED_ROSTER` overrides the roster file (default `~/.qoder-cn/skills/smart-subagent/roster.yml`). Auto-trigger every turn is enforced by a small rules file (`~/.qoder-cn/rules/token-speed.md`).

## Tests

66 unittest cases, stdlib only:

```bash
python -m unittest discover -s tests -t .
```

## Notes (field-tested)

- `request_id` lives **inside** `message.usage` — not on `message` or the row top level.
- Subagent turns share the event log; their `turn_id` equals the session id. That equality is what separates the 主 and 子 segments; they are excluded only when picking which turn is "current".
- `usage.speed` is a tier label (`"standard"`), not a numeric speed.
- With concurrent Qoder sessions, the newest log file is not necessarily yours — the script picks its segment by command anchor (the invocation's shell command contains `tokspeed.py`).
- Duration comes from `request.started → response.completed`; a retried request (`attempt_failed`) measures from its first `started`.
- Subagent requests keep their `usage` only in `subagents/agent-a*.jsonl` transcripts (the parent session jsonl lacks it); the script merges them, so subagent rows get real tok/s too.
