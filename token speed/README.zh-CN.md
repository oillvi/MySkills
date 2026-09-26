[English](README.md) | **简体中文**

# token-speed

在 Qoder 会话**每轮回合末尾追加一行真实 token 速度统计**：输出 TPS、耗时、缓存命中率、token 用量（M）、用了哪些模型——数据来自 Qoder 本地会话日志，不做任何估算。

## 报告什么

主会话一行；用了子智能体则**每个子模型各占一行**（用户裁定 2026-09-26）：

```
tok/s: 主 125 req · 35.8 tok/s · out 125.0k · 3494.5s · cache 90.5% · 19.070M
tok/s: 子 mimo-v2.6-flash×151 · 59.0 tok/s · out 153.2k · 2598.0s · cache 90.0% · 3.106M
```

多个子模型就是多条子行（按请求数降序、名字升序）。本回合没有子智能体时只有一行，也不带「主」字：

```
tok/s: 13 req · 39.0 tok/s · out 31.1k · 798.6s · cache 91.7% · 2.690M
```

- **tok/s** — 每行各自 Σ输出 token ÷ Σ耗时，只算该行有真实 usage 的请求。token 与耗时按 `request_id` 在事件日志（`model.request.started → model.response.completed`）与会话 jsonl（`message.usage`）之间配对
- **主 / 子分行** — 主行只统计主会话请求；每条子行只统计「`turn_id == session_id` 且属于该模型」的请求。tok/s、out、耗时、cache、M 全部逐行独立。没有「子合计」行——不同模型的速度掺在一起没有意义。事件里查不到模型名的请求进 `未标注` 子行，不静默丢
- **cache** — `cache_read_input_tokens / input_tokens`，**按行、按本回合窗口**算，不是整场任务的累计命中率
- **M** — `(input + cache_creation + output) / 1e6`，按行
- **models** — 主行只在跨多个模型、或整行无上报（需要知道是哪个模型）时才列各模型独立 tok/s；单模型主行不列——那等于把主模型速度重复一遍。子行把模型名放在计数位（`子 flash×151`），因此不再出现 `models:`。短名取 `/` 后段；UUID 形态按花名册（smart-subagent `roster.yml`）换别名，如 `4e190e86-…` → `deepseek-flash`；某模型无上报时标 `无上报`，不显示 0
- 通道不落 usage 时显示 `无 token 上报`，只给耗时——绝不显示假 0
- 窗口 = 本回合起点之后 started 的全部已完成请求；正在生成的最后一条回复永远不计入（它产生于统计之后；自 2026-09-26 起行尾不再打这句提示）

## 安装与运行

纯标准库、只读、单文件：

```bash
python ~/.qoder-cn/skills/token-speed/tokspeed.py
```

环境变量 `QODER_CN_HOME` 可重定向日志根（默认 `~/.qoder-cn`），测试用；`TOKENSPEED_ROSTER` 可指定花名册文件（默认 `~/.qoder-cn/skills/smart-subagent/roster.yml`）。每轮自动触发由小规则文件 `~/.qoder-cn/rules/token-speed.md` 强制。

## 测试

66 条 unittest，零依赖：

```bash
python -m unittest discover -s tests -t .
```

## 踩坑记录（实测）

- `request_id` 在 **`message.usage` 内部**，不在 `message` 层，也不在行顶层。
- 子智能体回合与主会话混在同一事件日志，其 `turn_id` 等于会话 id——这正是**分开两段**的判据；只在判断「哪个是当前回合」时排除它。
- `usage.speed` 是档位字符串（`"standard"`），不是数值速度。
- 多会话并发时 mtime 最新的日志不一定是你的——脚本按命令锚定（调用命令文本含 `tokspeed.py`）选自己的 segment。
- 耗时 = `request.started → response.completed`；重试请求（`attempt_failed` 后再次 started）从**第一次** started 计时。
- 子智能体请求的 `usage` 只落在 `subagents/agent-a*.jsonl` 转录里（父会话 jsonl 不含）；脚本会自动兼读，所以每条子行报的是真 tok/s，不是「无上报」。
