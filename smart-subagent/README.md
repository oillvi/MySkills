**English** | [简体中文](README.zh-CN.md)

# smart-subagent — delegate scouting & execution to pinned cheap subagents

The main thread only orchestrates: *think → write a dispatch brief → accept*. The legwork goes to purpose-built subagents pinned to cheap models: **glm-scout** (read-only reconnaissance, GLM-5.3-Flash) and **ds-coder** (write & run, DeepSeek-V4.1-Flash).

## The problem it solves

Installing subagents is not the same as using them. Baseline measured in this repo (`test-artifacts/baseline/REPORT.md`): across 5 typical scouting/execution tasks the main thread did **5/5 of the work itself** — the cheap specialist agents were never dispatched. This skill turns *who to dispatch, how to brief them, and how to accept their work* into an executable protocol.

## How it works

- **Decision table**: coordinate questions → glm-scout; construction work (bounded + verifiable) → ds-coder; design questions and one-step edits → stay with the main thread
- **Dispatch brief recipe**: task / scope / deliverable / acceptance criteria / prohibitions (subagents cannot see your session — the brief must be self-contained)
- **Acceptance protocol**: spot-check `path:line` claims, re-run the key command, route out-of-scope findings back to the main thread — a subagent's "done" does not count
- **Operational constraints**: subagents never git-commit (blocked by the permission classifier), the junction is a single point of failure, plus audit paths and token-accounting realities

## Triggering (measured)

| Path | Reliability |
|---|---|
| Explicitly saying「用便宜模型」/「派子智能体」/「use smart-subagent」 | ✅ 2/2 dispatched in tests |
| Model picks it up on its own (description only) | ❌ 0/4 in tests — say it explicitly |

When dispatched correctly, model pinning held 100% of the time (glm-scout ran entirely on GLM-5.3-Flash — see `test-artifacts/green/REPORT.md`).

## Install

1. Junction this skill folder into your agent's skills directory
2. Junction `agents/` to `~/.qoder-cn/agents` (**`mklink` is blocked by the permission classifier — use the python command instead**)
3. Verify: `cd ~/.qoder-cn/bin/qoderclicn && env -u QODER_AGENT_SDK_ENTRYPOINT ./qoderclicn.exe agents list` should report 7 agents (5 built-in + glm-scout + ds-coder)

Full commands and troubleshooting: [`reference/agent-authoring.md`](./reference/agent-authoring.md).

## Evidence

- `test-artifacts/baseline/REPORT.md` — red: 5/5 no dispatch before the skill
- `test-artifacts/green/REPORT.md` — green: 3 rounds / 15 sessions; explicit path fully working, autonomous triggering limits, execution-block status
- `test-artifacts/*/*.log` — raw per-session outputs

## License

[MIT](../LICENSE)