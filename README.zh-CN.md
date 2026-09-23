**English** | [简体中文](README.zh-CN.md)

# MySkills — Agent Skills 合集

个人编写的 Agent Skills 合集。每个子目录是一个独立技能，含 `SKILL.md`（遵循 [Agent Skills 规范](https://agentskills.io)的 frontmatter + 正文），可被任何支持该规范的 AI agent 加载。

English version: see [README.md](README.md).

## 技能列表 / Skills

### [turn-recap-format](./turn-recap-format/)

让 agent 把每轮回复自动组织成**四段式工作汇报**：【问题】（复述意图与假设）、【操作】（真实发生的动作清单）、【结果】（证据与状态）、【总结】（结论与待决项）——本轮确有显著低效时追加条件性第五段【弯路】。

- **触发时机**：当本轮最后一条面向用户的消息在 200–2000 字符区间时自动生效；过短直接答、过长走普通排版，主要产物是可复制文件时不套框架
- **解决的问题**：agent 干完活只丢一句"已完成"，用户看不到做了什么、证据在哪、还有什么要拍板——四段式把这几样强制摊开
- **条件性【弯路】段**：真实低效——折返重来、失败重试、子智能体产出没用上——逐条点名代价与更短路径；干净轮整段不写
- **内置防走样清单**：常见坏味道（复述原话、把计划当操作、结论混进证据槽、把浪费包装成后续提议）逐一列出修法

详见 [turn-recap-format/README.zh-CN.md](./turn-recap-format/README.zh-CN.md)。

### [smart-subagent](./smart-subagent/)

让主线程只做编排，跑腿的活交给钉了便宜模型的子智能体——**glm-scout**（GLM-5.3-Flash，只读勘察）与 **ds-coder**（DeepSeek-V4.1-Flash，有界执行）。

- **触发方式**：显式说「用便宜模型」「派子智能体」实测 2/2 可靠；模型自主调用不可靠（0/4），已在文档中如实标注
- **解决的问题**：基线实测主线程 5/5 场景全包——本技能给出分派决策表、自包含分派单配方与验收协议
- **随附本机硬核笔记**：Qoder CN 模型钉桩规矩、junction 的 python 修复法（`mklink` 会被权限分类器拦）、transcript 审计路径

详见 [smart-subagent/README.zh-CN.md](./smart-subagent/README.zh-CN.md)。

### [token-speed](./token%20speed/)

在 Qoder 会话**每轮回合末尾追加一行真实 token 速度统计**：输出 TPS、耗时、缓存命中率、token 用量（M）、用了哪些模型。

- **触发方式**：每轮自动（由小规则文件 `~/.qoder-cn/rules/token-speed.md` 强制），也可随问随查 token 速度 / TPS
- **解决的问题**：Qoder 界面只给 Credits，真实逐请求 token 藏在本地 jsonl 里。本技能如实摊开：按 `request_id` 配对事件日志与 jsonl 得真 tok/s，通道不落 usage 时报 `无 token 上报`（带耗时）而非假 0
- **随附踩坑记录**：`request_id` 在 `message.usage` 内部；子智能体回合混在同一事件日志（`turn_id` = 会话 id）；多会话并发时 mtime 最新不一定是自己——按命令锚定选 segment

详见 [token speed/README.zh-CN.md](./token%20speed/README.zh-CN.md)。

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
