# MySkills — Agent Skills 合集

个人编写的 Agent Skills 合集。每个子目录是一个独立技能，含 `SKILL.md`（遵循 [Agent Skills 规范](https://agentskills.io)的 frontmatter + 正文），可被任何支持该规范的 AI agent 加载。

**English:** A collection of Agent Skills written by me. Each subdirectory is a standalone skill with a `SKILL.md` file (frontmatter + instructions, following the Agent Skills spec), loadable by any AI agent that supports it.

## 技能列表 / Skills

### [turn-recap-format](./turn-recap-format/)

让 agent 把每轮回复自动组织成**四段式工作汇报**：【问题】（复述意图与假设）、【操作】（真实发生的动作清单）、【结果】（证据与状态）、【总结】（结论与待决项）。

- **触发时机**：当本轮最后一条面向用户的消息在 200–2000 字符区间时自动生效；过短直接答、过长走普通排版，主要产物是可复制文件时不套框架
- **解决的问题**：agent 干完活只丢一句"已完成"，用户看不到做了什么、证据在哪、还有什么要拍板——四段式把这几样强制摊开
- **内置防走样清单**：常见坏味道（复述原话、把计划当操作、结论混进证据槽）逐一列出修法

详见 [turn-recap-format/README.md](./turn-recap-format/README.md)。

## 安装 / Install

把技能目录放入你的 agent 的 skills 目录即可。以 Claude Code 为例（Windows 下用 junction 链接，本地改动与仓库保持同步）：

```bat
git clone https://github.com/oillvi/MySkills.git
mklink /J "%USERPROFILE%\.claude\skills\turn-recap-format" "<克隆路径>\MySkills\turn-recap-format"
```

其它 agent 同理：找到它的 skills 目录，把技能文件夹复制或链接进去。

## 使用 / Usage

agent 会按各技能 `SKILL.md` 中的 description 自动触发；多数实现也支持显式调用，如 `/四段`、`/recap`。

## License

[MIT](./LICENSE)
