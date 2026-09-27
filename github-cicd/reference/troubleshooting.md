# 失败对照表：先查表，再读日志

排查顺序永远是：`gh run view <id> --log-failed` 拿到失败步骤 → 在下表找现象 → 按「怎么确认」验证猜测 → 再改。
不要一上来就读全量日志（`--log`），几万行会淹掉关键行。

## A. 根本没触发（推了代码但 Actions 没动静）

| 现象 | 常见原因 | 怎么确认 | 修法 |
|---|---|---|---|
| `gh run list` 空 | 文件不在 `.github/workflows/` 下，或后缀不是 `.yml`/`.yaml` | `ls .github/workflows` | 移正路径 |
| 只有默认分支才触发 | `on: push` 未指定 branches 时行为与 PR 事件不同；`pull_request` 只看目标分支 | `gh workflow view <name>` 看 on 段 | 明确写 `branches:` / 用 `pull_request` |
| 改了文档不触发 | `paths-ignore` 命中（这是预期的） | 看 on 段的 paths/paths-ignore | 需要触发时改被监听路径下的文件 |
| 工作流被禁用 | 之前 disable 过，或长期失败被自动禁用 | `gh workflow list`（看是否列出） | `gh workflow enable <name>` |
| fork PR 不跑 | 仓库设置要求首次贡献者的运行需审批 | Actions 页面有 `action_required` 状态 | `gh run list --status action_required`，人工批准 |
| YAML 语法错 | 缩进/制表符/中文引号 | `python -c "import yaml,..."` 或 actionlint | 本地校验后再推（SKILL.md §4） |

## B. 触发了但立刻挂（权限与配置类）

| 现象 | 常见原因 | 怎么确认 | 修法 |
|---|---|---|---|
| 推 workflow 文件被拒 | 本机 token 缺 `workflow` scope | `gh auth status` 看 Token scopes | `gh auth refresh -h github.com -s workflow` |
| job 里 API 调用 403 | 顶层 `permissions: contents: read` 太窄，或默认 token 权限不足 | 日志里 403 的那条请求 | 给具体 job 加所需 `permissions:`（如发版要 `contents: write`），不要图省事开全局 write |
| secret 读出来是空 | 名字打错；或 secret 配在环境级而 job 没声明 `environment:`；或 fork PR 拿不到 secrets | `gh secret list` 核对名字 | 改名 / 在 job 上加 `environment:` / fork 场景改用 `pull_request_target`（**有安全风险，先读官方部署加固文档**） |
| 第三方 action 拉不到 | 版本 tag 不存在或改名 | 日志里 checkout action 的那行 | 钉到确切 tag 或 commit sha（`github/gh-actions-lock`） |
| 私有仓库跑不动/额度用尽 | 免费分钟数或存储耗尽 | 账单页 / `concepts/billing-and-usage` 文档 | 加缓存、缩 matrix、改 public 或 self-hosted |

## C. 跑一半挂（环境与依赖类）

| 现象 | 常见原因 | 怎么确认 | 修法 |
|---|---|---|---|
| 本地过、CI 挂 | runner 是全新一次性环境，没装你本机的全局工具 | 日志里 command not found | 在 step 里显式安装；不要假设预装 |
| Windows/macOS 专属错 | `runs-on: ubuntu-latest` 与本地 OS 不同（换行符、路径分隔符、shell 差异） | 看 `runs-on` 与失败命令 | 明确 `shell:`；路径用 `/` 或引号；必要时上 matrix 覆盖多 OS |
| 装依赖超时 | 没配缓存，每次全量下载 | 日志里依赖安装步骤耗时 | setup action 开 `cache:`，或 `actions/cache` + lockfile 哈希 key |
| 缓存行为诡异 | key 命中了旧缓存 | `gh cache list` | `gh cache delete`；key 里带上 lockfile 哈希与 OS |
| job 之间找不到文件 | job 默认并行且**不共享磁盘** | 看是否跨 job 传文件 | 用 `actions/upload-artifact` + `download-artifact`，或用 `needs:` 串行 |
| 步骤顺序不对 | 同一 job 内 steps 才是顺序执行 | 读 YAML 结构 | 需要顺序就放同一 job；需要并行才拆 job |
| 表达式没被替换 | `${{ }}` 用错上下文，或该上下文在此事件下为空 | 日志里插值后的实际值 | 查 `concepts/workflows-and-actions/contexts`（哪些事件下有哪些字段） |
| 被取消（cancelled） | `concurrency` 取消了旧跑（预期行为） | `gh run list --status cancelled` | 正常，不必修；要保留旧跑就调整 concurrency group |

## D. 绿了但结果不对

| 现象 | 常见原因 | 怎么确认 | 修法 |
|---|---|---|---|
| 测试其实没跑 | step 写了但命令空转，或 `continue-on-error: true` 吞了失败 | `gh run view <id> -v` 看步骤结论 | 去掉 `continue-on-error`；确认退出码 |
| 产物拿不到 | 没 upload，或 retention 到期 | `gh run view <id> --json` / Actions 页面 artifacts | 加 `actions/upload-artifact@v4`；本地 `gh run download <id>` |
| PR 上仍不让合并 | 分支保护要求的 check 名字与 workflow 里的 job 名不一致 | `gh pr checks --required` | 对齐 check 名，或改分支保护规则 |
| 部署没生效 | `environment:` 需要人工审批，卡在等待 | `gh run list --status action_required` | 去环境页批准，或调整环境保护规则 |

## E. 重跑与收尾

```bash
gh run rerun <run-id> --failed        # 只重跑失败 job（省分钟数，首选）
gh run rerun <run-id> --debug         # 需要更详细日志时
gh run cancel <run-id>                # 跑歪了先止损
gh run delete <run-id>                # 清理
gh run download <run-id> -D ./out     # 取产物到本地看
```

## F. 还是看不出来时

1. `gh run view <id> --job <job-id> --log | tail -100` —— 只看那个 job 的尾部。
2. `gh extension install swfz/gh-annotations` 后看 annotation 聚合（错误/警告按行归类）。
3. `gh extension install nektos/gh-act` 本地复现（重，最后手段）。
4. 查官方文档：`docs/official-docs-map.md` 的「运维工作流运行」与「排障」组（`how-tos/troubleshoot-workflows`）。
