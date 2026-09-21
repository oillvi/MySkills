# MySkills — Qoder Skills 合集

个人编写的 [Qoder](https://qoder.com) Skill 合集。每个子目录是一个独立技能，含 `SKILL.md`（遵循 Anthropic Skill 规范的 frontmatter + 正文）。

**English:** A collection of [Qoder](https://qoder.com) skills written by me. Each subdirectory is a standalone skill with a `SKILL.md` file (frontmatter + instructions, following the Agent Skills spec).

## 技能列表 / Skills

| 技能 | 说明 |
|------|------|
| [turn-recap-format](./turn-recap-format/) | 每轮回复四段式：【问题】【操作】【结果】【总结】。当本轮最后一条面向用户的消息在 200–2000 字符区间时生效，把工作汇报结构化。 |

## 安装 / Install

把技能目录放入 Qoder 的 skills 目录即可（Windows 示例）：

```bat
git clone https://github.com/<你的用户名>/MySkills.git
mklink /J "%USERPROFILE%\.qoder-cn\skills\turn-recap-format" "<克隆路径>\MySkills\turn-recap-format"
```

或者直接把技能文件夹复制到 `~/.qoder-cn/skills/` 下。用 junction 链接的好处是本地修改和仓库保持同步。

## 使用 / Usage

技能由 Qoder 按各技能 `SKILL.md` 中的 description 自动触发，也可显式调用，如 `/四段`、`/recap`。

## License

[MIT](./LICENSE)
