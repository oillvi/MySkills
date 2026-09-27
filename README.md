**English** | [简体中文](README.zh-CN.md)

# MySkills — Agent Skills Collection

A collection of Agent Skills written by me. Each subdirectory is a standalone skill with a `SKILL.md` file (frontmatter + instructions, following the [Agent Skills spec](https://agentskills.io)), loadable by any AI agent that supports it.

**简体中文：** 个人编写的 Agent Skills 合集，每个子目录是一个独立技能，可被任何支持该规范的 AI agent 加载。中文说明见 [README.zh-CN.md](README.zh-CN.md)。

## Skills

### [turn-recap-format](./turn-recap-format/)

Makes an AI agent automatically organize each turn's final reply into a **four-section work recap**: 【问题】(intent & assumptions), 【操作】(actions actually taken), 【结果】(evidence & status), 【总结】(conclusion & open decisions) — plus a conditional fifth section 【弯路】(detours) when the turn had real inefficiency.

- **When it triggers**: applies when the turn's final user-facing message falls in the 200–2000 character range; shorter replies stay plain, longer ones use regular formatting, and turns whose deliverable is a copyable file skip the frame entirely
- **The problem it solves**: agents tend to end work with a bare "done" — no record of what was done, no verifiable evidence, and decisions the user needs to make buried in prose. The four sections force all three into the open
- **Conditional detours section**: real waste — retraced steps, failed retries, unused subagent output — is named with its cost and the shorter path in 【弯路】; clean turns omit the section entirely
- **Built-in anti-pattern checklist**: common failure modes (parroting the user's words, reporting plans as actions, conclusions leaking into the evidence section, repackaging waste as follow-up offers) are each paired with a fix

See [turn-recap-format/README.md](./turn-recap-format/README.md) for details.

### [smart-subagent](./smart-subagent/)

Makes the main thread orchestrate while the pinned cheap subagent does the legwork — **mimo-worker** (mimo-v2.6-flash, reconnaissance & bounded edits/runs).

- **When it triggers**: reliably on explicit asks like「用便宜模型」「派子智能体」/ "use smart-subagent" (2/2 in tests); silent auto-pickup is unreliable (0/4) and documented as-is
- **The problem it solves**: a measured baseline shows the main thread doing 5/5 scouting/execution tasks itself even with cheap specialist agents installed — this skill adds a dispatch decision table, a self-contained brief recipe, and an acceptance protocol
- **Hard-won operator notes**: Qoder CN model-pinning rules, junction repair via python (`mklink` gets blocked), transcript-based auditing

See [smart-subagent/README.md](./smart-subagent/README.md) for details.

smart-subagent also ships a watchdog probe, `tools/probe.py` (with `--fine coder|scout` fine probes): stuck or looping subtasks are handled with graded WARN/BLOCK. It also ships `tools/tasktime.py`, which reports each subtask's real wall time (`createdAt→completedAt`) — the chat card's "Subagent completed in Xs" is anchored to the ~4s async-launch tool call and understates the real run.

### [token-speed](./token%20speed/)

Appends **real token-speed stats** to the end of every assistant turn in a Qoder session: output TPS, duration, cache hit rate, token usage (M), and which models ran — one line for the main session, plus **one line per subagent model** whenever subagents were used.

- **When it triggers**: every turn, enforced by a tiny rules file (`~/.qoder-cn/rules/token-speed.md`); also answers on-demand token speed / TPS questions
- **The problem it solves**: Qoder's UI shows Credits only — real per-request token data hides in local jsonl logs. This surfaces it honestly: true tok/s via `request_id` pairing of event log and jsonl, and `no usage reported` (with duration) instead of fake zeros for channels that don't report
- **Main vs subagent**: main-session and subagent numbers never share a figure — each line reports its own tok/s / out / duration / cache / M, so a fast cheap subagent can no longer inflate the main turn's speed, and the main model's number is not repeated in a `models:` list
- **Hard-won operator notes**: `usage.request_id` lives inside `message.usage`; subagent turns share the event log (`turn_id` == session id, which is the split key); with concurrent sessions the newest log file may not be yours — pick the segment by command anchor

See [token speed/README.md](./token%20speed/README.md) for details.

## Install

Put the skill directory into your agent's skills directory. For example, with Claude Code on Windows (a junction keeps local edits in sync with the repo):

```bat
git clone https://github.com/oillvi/MySkills.git
mklink /J "%USERPROFILE%\.claude\skills\turn-recap-format" "<clone path>\MySkills\turn-recap-format"
```

Other agents work the same way: locate the agent's skills directory and copy or link the skill folder into it.

## Usage

The agent triggers each skill automatically based on its `SKILL.md` description; most implementations also support explicit invocation such as `/recap`.

## License

[MIT](./LICENSE)
