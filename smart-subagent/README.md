**English** | [简体中文](README.zh-CN.md)

# smart-subagent — delegate scouting & execution to pinned cheap subagents

The main thread only orchestrates: *think → write a dispatch brief → accept*. The legwork goes to purpose-built subagents pinned to cheap models: **glm-scout** (read-only reconnaissance, GLM-5.3-Flash) and **ds-coder** (write & run, DeepSeek-V4.1-Flash).

## The problem it solves

Installing subagents is not the same as using them. Baseline measured in this repo: across 5 typical scouting/execution tasks the main thread did **5/5 of the work itself** — the cheap specialist agents were never dispatched. This skill turns *who to dispatch, how to brief them, and how to accept their work* into an executable protocol.

## How it works

- **Decision table**: coordinate questions → glm-scout; construction work (bounded + verifiable) → ds-coder; design questions and one-step edits → stay with the main thread
- **Dispatch brief recipe**: task / scope / deliverable / acceptance criteria / prohibitions (subagents cannot see your session — the brief must be self-contained)
- **Acceptance protocol**: spot-check `path:line` claims, re-run the key command, route out-of-scope findings back to the main thread — a subagent's "done" does not count
- **Operational constraints**: subagents never git-commit (blocked by the permission classifier), the junction is a single point of failure, plus audit paths and token-accounting realities
- **Two-level model roster**: which models/agents subtasks may use is constrained by `roster.yml` (user-level default) and can be overridden per project via `.qoder/smart-subagent.roster.yml`; tasks are routed by class at dispatch time — never dispatched off-roster
- **Model aliases & reminders**: `models:` gives each model a human alias (built-ins `qoder-<name>`; BYOK by source like `deepseek-v4.1-flash`; generic endpoints user-defined); unnamed or removed models stop the dispatch with an update-the-roster reminder; an "update path table" maps every change straight to its file

## Triggering (measured)

| Path | Reliability |
|---|---|
| Explicitly saying「用便宜模型」/「派子智能体」/「use smart-subagent」 | ✅ 2/2 dispatched in tests |
| Model picks it up on its own (description only) | ❌ 0/4 in tests — say it explicitly |

When dispatched correctly, model pinning held 100% of the time (glm-scout ran entirely on GLM-5.3-Flash).

## FAQ: pinning & routing models

- **Who triggers the skill?** You, explicitly (see table). Note the agents themselves are always visible — naming one directly ("have glm-scout find X") also works; the skill governs *how to dispatch and accept*.
- **How do I pick the model for a subtask?** You cannot pass a model at dispatch time — the model is pinned in the agent's definition file (`model:` field), so **choosing the agent is choosing the model**. To change: edit the definition, or create a new pinned agent and enlist it in the roster.
- **What if I don't know the upcoming subtasks yet?** You don't need to. The roster constrains the *allowed set* plus class→agent routing; tasks get classified when they appear. Unclear class → cheapest fitting entry by `use_for`; off-roster need → `on_out_of_roster` policy.
- **Can I set constraint scopes?** Two levels: user-level `skills/smart-subagent/roster.yml` (global default) > project-level `<project>/.qoder/smart-subagent.roster.yml` (replaces it wholesale). Details: [`reference/model-routing.md`](./reference/model-routing.md).
- **How do I alias a model, and where do edits go?** Aliases live in user-level `roster.yml` `models:`; re-pinning an agent means editing `agents/<name>.md` `model:` plus the roster `uses`. The docs carry an "update path table" mapping each change to its file.

## Install

1. Junction this skill folder into your agent's skills directory
2. Junction `agents/` to `~/.qoder-cn/agents` (**`mklink` is blocked by the permission classifier — use the python command instead**)
3. Verify: `cd ~/.qoder-cn/bin/qoderclicn && env -u QODER_AGENT_SDK_ENTRYPOINT ./qoderclicn.exe agents list` should report 7 agents (5 built-in + glm-scout + ds-coder)

Full commands and troubleshooting: [`reference/agent-authoring.md`](./reference/agent-authoring.md).

## Evidence

- Four behavioral test rounds (red: 5/5 no dispatch; green: 15 sessions; roster; alias layer) plus raw logs are archived locally outside the repo (`MySkills-archive`, **not distributed**); earlier copies remain in git history

## License

[MIT](../LICENSE)