**English** | [简体中文](README.zh-CN.md)

# token-speed

Appends one line of **real token-speed stats** to the end of every assistant turn in a Qoder session: output TPS, duration, cache hit rate, token usage (M), and which models ran — computed from Qoder's local session logs, never estimated.

**简体中文：** 每轮回合末尾自动追加一行真实 token 速度统计（TPS / 耗时 / 缓存命中率 / 用量 M / 使用的模型），数据来自 Qoder 本地会话日志，不做估算。中文说明见 [README.zh-CN.md](README.zh-CN.md)。

## What it reports

```
tok/s: 13 req · 39.0 tok/s · out 31.1k · 798.6s · cache 91.7% · 2.690M · models: mimo-v2.6-pro×13 · 末条回复不计
```

- **tok/s** — total output tokens ÷ total duration, over requests with real usage only. Tokens and timing are paired by `request_id` between the event log (`model.request.started → model.response.completed`) and the session jsonl (`message.usage`)
- **cache** — `cache_read_input_tokens / input_tokens`
- **M** — `(input + cache_creation + output) / 1e6`
- **models** — per-model request counts (short name after `/`), subagent/background requests included
- Channels that report no usage show `无 token 上报` ("no usage reported") with duration only — never a fake 0
- Window = all completed requests started after the current turn began; the in-flight final reply is never included (it postdates the measurement, hence the `末条回复不计` tail note)

## Install & run

Pure stdlib, read-only, single file:

```bash
python ~/.qoder-cn/skills/token-speed/tokspeed.py
```

`QODER_CN_HOME` overrides the log root (default `~/.qoder-cn`) for testing. Auto-trigger every turn is enforced by a small rules file (`~/.qoder-cn/rules/token-speed.md`).

## Tests

31 unittest cases, stdlib only:

```bash
python -m unittest discover -s tests -t .
```

## Notes (field-tested)

- `request_id` lives **inside** `message.usage` — not on `message` or the row top level.
- Subagent turns share the event log; their `turn_id` equals the session id. They are counted in (user decision), and excluded only when picking which turn is "current".
- `usage.speed` is a tier label (`"standard"`), not a numeric speed.
- With concurrent Qoder sessions, the newest log file is not necessarily yours — the script picks its segment by command anchor (the invocation's shell command contains `tokspeed.py`).
- Duration comes from `request.started → response.completed`; a retried request (`attempt_failed`) measures from its first `started`.
