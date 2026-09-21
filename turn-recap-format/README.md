**English** | [简体中文](README.zh-CN.md)

# turn-recap-format — Four-Section Work Recap

Makes an AI agent automatically structure each turn's final reply in a conversation into a four-section work recap, replacing bare "done" replies.

简体中文版见 [README.zh-CN.md](README.zh-CN.md)。

## What problem it solves

Agents typically end a turn in one of three vague ways: no record of what was done, no verifiable evidence, and decisions the user needs to make buried in prose. This skill uses a fixed frame to force all three into the open — and only applies where the reply length warrants it: no frame for three-line answers, no frame for hundred-line reports.

## The four sections

```text
【问题】<One sentence restating the user's intent + the assumption I made for you, choosing A over B>
【操作】<Verb-led action list, each item matching a real tool call or file write, max 5>
【结果】<Evidence: numbers, paths, quotes, grouped by topic; every conclusion carries a status tag: verified / to-confirm / out-of-scope / n/a>
【总结】<One-line conclusion + tiered open items: [must-decide] [suggested] [optional] [awaiting-you], one per line>
```

An example (what a reply looks like after the agent fixes a bug):

> 【问题】You want the login timeout fixed; I assumed 30 seconds is the product default, so I only touched configuration, not code.
> 【操作】- Reproduced the timeout path; - Located the session middleware; - Modified `config.py:42`; - Ran 12 regression tests
> 【结果】**Tests (verified)**: 12/12 pass, timeout path returns in 0.8s; **Change (verified)**: single file, +2/-2 lines
> 【总结】
> - **[awaiting-you] Ship it?**: the fix contains no other changes, so it can go out as a standalone patch.
> - **[suggested] Monitoring**: watch the timeout rate for a week after release.

## Trigger rules

| The turn's final message | Behavior |
|---|---|
| Under ~200 characters | Answer directly, no frame |
| 200–2000 characters | Apply the four-section frame |
| Over ~2000 characters | Regular formatting (headings, tables) |
| Main deliverable is a copyable file/code | Deliver the artifact only, no frame |
| User specified a format | Do what the user asked |

The frame governs only the **final** message of a turn; no section headings between tool calls. A built-in "common failure → fix" checklist covers a dozen-plus failure modes (parroting the original request, reporting plans as actions, conclusions leaking into the evidence section, etc.), plus coexistence rules for canvas artifacts and minimalist modes.

## Install

Put this directory (including `SKILL.md`) into your agent's skills directory, or link it to stay in sync:

```bat
mklink /J "<agent's skills directory>\turn-recap-format" "<this repo path>\turn-recap-format"
```

## Usage

- **Automatic**: the agent triggers it based on the `SKILL.md` description
- **Explicit**: `/recap`, or say "use the four-section recap" in conversation
- **Disable**: say "turn off the recap format" and replies revert to normal for the session

## License

[MIT](../LICENSE)
