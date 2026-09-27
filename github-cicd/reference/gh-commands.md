# gh 命令速查（GitHub Actions 向）

本机实测环境：`gh version 2.101.0 (2026-09-15)`，Windows + Git Bash，账号 `oillvi`，Token scopes = `gist, read:org, repo, workflow`。
下面所有 flag 与 JSON 字段都来自本机 `gh <cmd> --help` 输出，不是凭记忆写的。标「未实测」的条目本机没有可验证对象。

## gh run —— 看运行

子命令：`list` `view` `watch` `rerun` `cancel` `delete` `download`

`gh run list` 关键 flag：

| flag | 作用 |
|---|---|
| `-L, --limit int` | 取多少条（默认 20） |
| `-s, --status string` | 见下方状态值 |
| `-b, --branch string` / `-c, --commit SHA` | 按分支 / 提交过滤 |
| `-e, --event event` | 按触发事件过滤（push、pull_request、workflow_dispatch…） |
| `-w, --workflow string` | 按工作流名过滤 |
| `-a, --all` | 含已禁用的工作流 |
| `--created date` / `-u, --user string` | 按日期 / 触发人过滤 |
| `--json fields` / `-q, --jq` / `-t, --template` | 结构化输出 |

`--status` 可用值（原文照抄）：`queued` `completed` `in_progress` `requested` `waiting` `pending` `action_required` `cancelled` `failure` `neutral` `skipped` `stale` `startup_failure` `success` `timed_out`

`gh run list` / `gh run view` 的 JSON 字段：
`attempt` `conclusion` `createdAt` `databaseId` `displayTitle` `event` `headBranch` `headSha` `name` `number` `startedAt` `status` `updatedAt` `url` `workflowDatabaseId` `workflowName`

`gh run view` 关键 flag：`--log`（全量日志）、`--log-failed`（只看失败步骤，排障首选）、`-j, --job <id>`、`-a, --attempt <n>`、`-v, --verbose`（显示 job 内步骤）、`--exit-status`（失败则非零退出，适合脚本里用）、`-w, --web`。

`gh run rerun` 关键 flag：`--failed`（只重跑失败 job 及其依赖，省分钟数）、`-j, --job <id>`、`-d, --debug`（开 debug 日志重跑）。

`gh run download`：下载产物（`-n <name>` 指定产物名，`-D <dir>` 指定落盘目录；flag 细节以 `gh run download --help` 为准）。

## gh workflow —— 看/触发工作流文件

子命令：`list` `view` `run` `enable` `disable`

`gh workflow run` 关键 flag：`-r, --ref <branch|tag>`（用哪个分支上的工作流版本）、`-f, --raw-field key=value`、`-F, --field key=value`（支持 `@file` 语法）、`--json`（从 stdin 读 inputs）。
只能触发声明了 `workflow_dispatch` 的工作流。

## gh cache —— 缓存

子命令：`list` `delete`。缓存 key 撞车或依赖变更后行为诡异时，先 `gh cache list` 看 key，再 `gh cache delete`。

## gh secret / gh variable —— 密钥与变量

`gh secret`：`set` `list` `delete`
`gh secret set` 关键 flag：`-b, --body`（不给则从 stdin 读）、`-a, --app {actions|agents|codespaces|dependabot}`、`-e, --env <environment>`（环境级 secret）、`-f, --env-file <file>`（dotenv 批量）、`-o, --org` + `-v, --visibility {all|private|selected}` + `-r, --repos`（组织级）、`-u, --user`（用户级）、`--no-store`（只打印加密后的 base64，不落库）。

`gh variable`：`set` `get` `list` `delete`（非敏感配置放 variable，日志里可见；敏感的必须放 secret）。

## gh pr checks —— PR 视角的 CI 状态

`gh pr checks [<number>|<url>|<branch>]`，flag：`--watch`、`--fail-fast`（首个失败即退出 watch）、`--required`（只看必需检查）、`-i, --interval <秒>`（默认 10）、`-w, --web`。
**退出码 8 = 检查仍在 pending**（脚本里要区分「还没跑完」和「跑挂了」）。`--json` 输出含 `bucket` 字段，把 state 归类为 `pass` `fail` `pending` `skipping` `cancel`。

## gh api —— 万能兜底（本机最重要的两条用法）

```bash
# 1) 读官方文档源码（WebFetch 抓 docs.github.com 在本机必超时）
gh api "repos/github/docs/contents/content/actions/get-started/quickstart.md" \
  -H "Accept: application/vnd.github.raw+json"

# 2) 读官方 workflow 模板（curl 直连 raw.githubusercontent.com 会超时）
gh api "repos/actions/starter-workflows/contents/ci/blank.yml" \
  -H "Accept: application/vnd.github.raw+json"
```

REST 端点 `repos/{owner}/{repo}/actions/runs/{run_id}/timing`（单次 run 的耗时明细）——**未实测**（本机暂无 run 可验），需要精确分钟数时用它或 MCP 的 `get_workflow_run_usage`。

## gh skill —— 官方技能通道（preview）

子命令：`search` `install` `preview` `list` `update` `publish`（别名 `gh skills`）。

`gh skill install` 关键 flag：`--agent <host>`（支持列表里**含 `qoder`**）、`--scope {project|user}`（默认 project）、`--dir <path>`（**覆盖** `--agent` 与 `--scope`，直接指定安装目录）、`--all`、`-f, --force`、`--pin <tag|sha>`、`--from-local`、`--allow-hidden-dirs`、`--upstream`。

⚠️ 本机必须用 `--dir`：gh 源码 `internal/skills/registry/registry.go` 里 qoder 的 ProjectDir/UserDir 都是 `.qoder/skills`，而本机 Qoder CN 读的是 `C:\Users\浪\.qoder-cn\skills`（两目录实测不同：41 项 vs 29 项，`smart-subagent`/`token-speed`/`turn-recap-format` 只在 `.qoder-cn`）。

```bash
gh skill install github/awesome-copilot github-actions-hardening --dir "C:\Users\浪\.qoder-cn\skills"
gh skill list --agent qoder --scope user --json skillName,path   # 验证装到哪了
```

`gh skill publish`：按 agentskills.io 规范校验并建 GitHub release。发现规则：`skills/*/SKILL.md`、`skills/{scope}/*/SKILL.md`、根级 `*/SKILL.md`、`plugins/{scope}/skills/*/SKILL.md`。校验点：名字符合命名规则、**技能名必须与目录名一致**、frontmatter 必须有 `name` 与 `description`、`allowed-tools` 是字符串不是数组。flag：`--dry-run`（只校验）、`--tag`（非交互发版）、`--fix`（剥离 install 元数据）。

## 常用一行命令（recipes）

```bash
run_id=$(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')   # 最近一次 run
gh run view "$run_id" --log-failed                                          # 只看失败步骤
gh run list --status failure --limit 5                                      # 最近 5 次失败
gh run watch "$run_id" --exit-status && echo GREEN || echo RED              # 跟到结束并给结论
gh pr checks --watch --fail-fast                                            # PR 上等 CI
gh workflow list                                                            # 仓库里有哪些工作流
gh secret list                                                              # 配了哪些 secret（只列名，不显值）
```

## 值得装的 gh 扩展（按需）

| 扩展 | 用途 |
|---|---|
| `cschleiden/gh-actionlint` | lint workflow YAML，推送前抓语法/表达式错 |
| `nektos/gh-act` | 本地跑 Actions（重，反复失败时才用） |
| `github/gh-actions-lock` | 生成/校验依赖锁文件，把每个 action 钉到确切 commit |
| `github/gh-aw` | GitHub Agentic Workflows（官方，5.2k★） |
| `github/gh-actions-importer` | 从 Jenkins / GitLab CI / CircleCI / Travis / Azure DevOps 迁移 |
| `fchimpan/gh-workflow-stats` | 算工作流成功率与耗时 |
| `swfz/gh-annotations` | 列最近运行的 annotation（错误/警告聚合） |

## 官方 MCP Server（可选补充）

仓库 `github/github-mcp-server`（官方，33k★）。远程端点按 toolset 切 URL：

- `https://api.githubcopilot.com/mcp/` — 默认 toolset
- `https://api.githubcopilot.com/mcp/x/actions` — **GitHub Actions workflows and CI/CD operations**
- 任意 toolset 加 `/readonly` 变只读；`/x/all` 全量；组合多个用 header `X-MCP-Toolsets: repos,actions`
- 认证：OAuth 或 PAT（`Authorization: Bearer <token>`）

`actions` toolset 实测工具名（读自 `pkg/github/actions.go`）：`list_workflows` `get_workflow` `run_workflow` `list_workflow_runs` `get_workflow_run` `get_workflow_run_logs_url` `get_workflow_run_usage` `list_workflow_jobs` `get_workflow_job` `get_job_logs` `list_workflow_run_artifacts` `download_workflow_run_artifact` `rerun_workflow_run` `rerun_failed_jobs` `cancel_workflow_run` `delete_workflow_run_logs` `check_run`。

另有 `github_support_docs_search` toolset（检索 GitHub 官方文档，含 Actions Workflows 主题）。

**取舍**：gh CLI 已登录、能写文件、能提交，覆盖 95% 场景；MCP 的增量价值是结构化批量读 run/log/用量，以及 docs 检索。MCP **不能**把 YAML 写进仓库。
