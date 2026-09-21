**English** | [简体中文](README.zh-CN.md)

# MySkills — Agent Skills Collection

A collection of Agent Skills written by me. Each subdirectory is a standalone skill with a `SKILL.md` file (frontmatter + instructions, following the [Agent Skills spec](https://agentskills.io)), loadable by any AI agent that supports it.

**简体中文：** 个人编写的 Agent Skills 合集，每个子目录是一个独立技能，可被任何支持该规范的 AI agent 加载。中文说明见 [README.zh-CN.md](README.zh-CN.md)。

## Skills

### [turn-recap-format](./turn-recap-format/)

Makes an AI agent automatically organize each turn's final reply into a **four-section work recap**: 【问题】(intent & assumptions), 【操作】(actions actually taken), 【结果】(evidence & status), 【总结】(conclusion & open decisions).

- **When it triggers**: applies when the turn's final user-facing message falls in the 200–2000 character range; shorter replies stay plain, longer ones use regular formatting, and turns whose deliverable is a copyable file skip the frame entirely
- **The problem it solves**: agents tend to end work with a bare "done" — no record of what was done, no verifiable evidence, and decisions the user needs to make buried in prose. The four sections force all three into the open
- **Built-in anti-pattern checklist**: common failure modes (parroting the user's words, reporting plans as actions, conclusions leaking into the evidence section) are each paired with a fix

See [turn-recap-format/README.md](./turn-recap-format/README.md) for details.

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
