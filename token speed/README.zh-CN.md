[English](README.md) | **简体中文**

# token-speed

在 Qoder 会话**每轮回合末尾追加一行真实 token 速度统计**：输出 TPS、耗时、缓存命中率、token 用量（M）、用了哪些模型——数据来自 Qoder 本地会话日志，不做任何估算。

## 报告什么

```
tok/s: 13 req · 39.0 tok/s · out 31.1k · 798.6s · cache 91.7% · 2.690M · models: mimo-v2.6-pro×13 · 末条回复不计
```

- **tok/s** — Σ输出 token ÷ Σ耗时，只算有真实 usage 的请求。token 与耗时按 `request_id` 在事件日志（`model.request.started → model.response.completed`）与会话 jsonl（`message.usage`）之间配对
- **cache** — `cache_read_input_tokens / input_tokens`
- **M** — `(input + cache_creation + output) / 1e6`
- **models** — 各模型请求次数（取 `/` 后的短名），**含**子智能体/后台请求
- 通道不落 usage 时显示 `无 token 上报`，只给耗时——绝不显示假 0
- 窗口 = 本回合起点之后 started 的全部已完成请求；正在生成的最后一条回复永远不计入（它产生于统计之后，行尾 `末条回复不计` 即此意）

## 安装与运行

纯标准库、只读、单文件：

```bash
python ~/.qoder-cn/skills/token-speed/tokspeed.py
```

环境变量 `QODER_CN_HOME` 可重定向日志根（默认 `~/.qoder-cn`），测试用。每轮自动触发由小规则文件 `~/.qoder-cn/rules/token-speed.md` 强制。

## 测试

31 条 unittest，零依赖：

```bash
python -m unittest discover -s tests -t .
```

## 踩坑记录（实测）

- `request_id` 在 **`message.usage` 内部**，不在 `message` 层，也不在行顶层。
- 子智能体回合与主会话混在同一事件日志，其 `turn_id` 等于会话 id。按用户裁定**计入**统计；只在判断「哪个是当前回合」时排除。
- `usage.speed` 是档位字符串（`"standard"`），不是数值速度。
- 多会话并发时 mtime 最新的日志不一定是你的——脚本按命令锚定（调用命令文本含 `tokspeed.py`）选自己的 segment。
- 耗时 = `request.started → response.completed`；重试请求（`attempt_failed` 后再次 started）从**第一次** started 计时。
