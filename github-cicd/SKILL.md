---
name: github-cicd
description: 给任意项目搭建或修复 GitHub Actions CI/CD 流水线：仓库体检 → 选档位 → 从官方模板生成 workflow YAML → 本地校验 → 推送 → gh run watch 观测 → 失败三连诊断 → 出带 run URL 证据的报告；跨项目复用走 reusable workflow。当用户提到 CI/CD、流水线、GitHub Actions、workflow/工作流、自动测试/自动构建/自动发布、gh run、Actions 跑红了/挂了、部署自动化、多项目共用一条流水线时使用。Use when setting up or debugging GitHub Actions CI/CD in any repository — generate or repair workflow YAML from official templates, drive and observe runs with the gh CLI, diagnose failures, and share one pipeline across projects via reusable workflows.
---

# GitHub CI/CD（gh CLI 为手，官方文档为据）

主干只有一条：**体检 → 选档位 → 生成 → 本地校验 → 推送 → 观测 → 诊断 → 报告**。
每一环都用本机实测过的 `gh` 命令，不靠网页抓取（本机抓 docs.github.com 必超时，见 §10）。

## 0. 何时用 / 何时不用

**用**：给一个仓库从零搭 CI/CD；已有 workflow 跑红要排查；要把一条流水线复用到多个项目；要给项目加自动发布/部署环节。

**不用**：非 GitHub 平台（GitLab CI / Jenkins / CircleCI）——本技能只覆盖 GitHub Actions；纯本地脚本自动化（不涉及远端 runner）；只是想读一次 run 状态（直接 `gh run list` 即可，不必起流程）。

## 1. 先体检（每次动手前跑，输出贴进最终报告）

```bash
gh --version
gh auth status                                  # 看 Token scopes 里有没有 workflow
gh repo view --json name,owner,visibility,primaryLanguage,defaultBranchRef
ls .github/workflows 2>/dev/null                # 已有流水线？先读再改，别覆盖
```

判读要点：

| 体检项 | 不合格的表现 | 修法 |
|---|---|---|
| token scope | scopes 里没有 `workflow` | `gh auth refresh -h github.com -s workflow`（否则推 `.github/workflows` 会被拒） |
| 仓库可见性 | `PRIVATE` | Actions 分钟数有免费额度与 OS 倍率，先看 `docs/official-docs-map.md` 的「额度与限额」组 |
| 已有 workflow | 目录非空 | 先 `gh workflow list` + 读文件，改造而非新建，避免两条流水线重复烧分钟数 |
| 语言/构建工具 | — | 决定选哪个模板（§3） |

## 2. 选档位（三选一，别过度设计）

| 档位 | 内容 | 适用 | 起手模板 |
|---|---|---|---|
| **A 最小 CI** | push + PR 跑 lint/test | 个人项目、脚本仓、第一次上 CI | `templates/base/ci.yml` |
| **B 标准 CI + 发布** | A + tag 触发 build/release | 要出版本、制品、镜像 | `templates/base/ci.yml` + `release.yml` |
| **C 多项目复用** | 中心仓库放 reusable workflow，各项目一个 caller | **确实**有 ≥2 个同类项目要共用 | `templates/base/reusable-ci.yml` + `caller-example.yml` |

判据：只有真的存在第二个仓库要共用时才上 C（YAGNI）。从 A 起步、跑绿了再往 B/C 加，永远比一次到位便宜。

## 3. 生成 YAML

优先顺序：**本技能 `templates/base/`（已按最小权限写好）→ 官方 `actions/starter-workflows`（`templates/upstream/` 有存档，也可现取）→ 手写**。

现取官方模板（不要用 curl 直连 raw，本机超时）：

```bash
gh api "repos/actions/starter-workflows/contents/ci" --jq '.[].name'
gh api "repos/actions/starter-workflows/contents/ci/blank.yml" -H "Accept: application/vnd.github.raw+json"
```

**六条硬规矩**（每份 YAML 都要满足）：

1. 顶层 `permissions:` 收窄（默认 `contents: read`；只有发布 job 单独给 `contents: write`）。
2. `concurrency:` 取消同分支的旧跑，省分钟数。
3. 第三方 action 钉版本；生产仓库建议钉到 commit sha（扩展 `github/gh-actions-lock`）。
4. 依赖缓存：语言 setup action 自带 `cache:`，或 `actions/cache` + lockfile 哈希做 key。
5. secrets 只从 `gh secret set` 进，不写进 YAML、不 `echo`。
6. 触发条件带 `paths-ignore`（文档/README 改动不必触发全量 CI）。

## 4. 本地校验（推送前必须过，输出留证）

```bash
python -c "import yaml,sys;yaml.safe_load(open(sys.argv[1],encoding='utf-8'));print('OK',sys.argv[1])" .github/workflows/ci.yml
actionlint .github/workflows/*.yml 2>/dev/null || echo "actionlint 未安装（可用 gh extension install cschleiden/gh-actionlint）"
```

人工核对清单：缩进与顶层键（`on` / `jobs` / `permissions` / `concurrency`）、`needs:` 依赖顺序是否真的串行、`matrix` 会不会炸成 N 倍分钟数、`secrets.*` 是否都已在仓库里配好（`gh secret list`）。

⚠️ 用脚本校验时的坑：**PyYAML 会把 workflow 的 `on:` 键解析成布尔 `True`**（YAML 1.1 规范），所以 `d["on"]` 直接 KeyError——要写 `d.get("on", d.get(True))`。本机实测踩过。

反复失败又看不出原因时，才上本地模拟：`gh extension install nektos/gh-act`（重，慢，最后手段）。

## 5. 推送与观测

**git 提交由主线程做**（子智能体的提交会被权限分类器拦）；本机需要显式覆盖身份：

```bash
git add .github/workflows/ci.yml
git -c user.name="<你>" -c user.email="<你的邮箱>" commit -m "ci: add baseline workflow"
git push
```

推完立刻观测：

```bash
gh run list --limit 5 --json databaseId,status,conclusion,workflowName,headBranch,url
gh run watch <run-id>                    # 跟到结束
gh run view <run-id> --web               # 浏览器看
gh pr checks --watch --fail-fast         # PR 视角；退出码 8 = 还在跑
gh workflow run <name> -f key=value      # 手动触发 workflow_dispatch
```

命令与 JSON 字段全表见 `reference/gh-commands.md`。

## 6. 失败诊断三连

```bash
gh run view <run-id> --log-failed                       # 1 只看失败步骤
gh run view <run-id> --job <job-id> --log | tail -100    # 2 钻到具体 job
gh run rerun <run-id> --failed                          # 3 只重跑失败 job（省分钟数）
```

错因对照表（权限 403 / fork PR 拿不到 secrets / runner OS 差异 / 超时 / 被并发取消 / action 版本漂移 / 路径过滤器写错导致根本不触发）见 `reference/troubleshooting.md`——先查表，再读日志。

## 7. 跨项目通用化（这套流程要复用到别的项目时看这里）

机制是 **reusable workflow**：把流水线放在一个中心仓库（本机是 `oillvi/MySkills`），其它项目只放一个几行的 caller。改中心一处，所有项目生效。

```yaml
# 调用方仓库 .github/workflows/ci.yml
jobs:
  ci:
    uses: oillvi/MySkills/.github/workflows/reusable-ci.yml@main
    with:
      language-version: "3.12"
    # secrets: inherit   # 方便但等于把调用方全部 secrets 交出去，能不用就不用
```

版本策略：`@main` 省心但会被上游改动影响；`@v1`（tag）稳定但要发版。多项目、跨组织共享的官方做法见 `docs/official-docs-map.md` 的「复用与通用化」组。

## 8. 可选增强（按需，别默认装）

**官方 MCP Server（`github/github-mcp-server`）的 `actions` toolset**：远程端点 `https://api.githubcopilot.com/mcp/x/actions`（只读版加 `/readonly`），工具有 `list_workflow_runs`、`get_job_logs`、`run_workflow`、`rerun_failed_jobs`、`download_workflow_run_artifact`、`get_workflow_run_usage` 等。
值得用：需要结构化批量读 run/log/用量。不值得：只是想跑通一条流水线——`gh` 已经登录好了，而且 **MCP 不能把 YAML 写进仓库**，写文件仍然靠 git/gh。另有 `github_support_docs_search` toolset 可直接检索 GitHub 官方文档。

**gh 扩展**：`cschleiden/gh-actionlint`（lint）、`nektos/gh-act`（本地跑）、`github/gh-actions-lock`（钉 sha）、`github/gh-aw`（Agentic Workflows）、`github/gh-actions-importer`（从 Jenkins/GitLab CI 等迁移）。

**官方技能当知识底座**：`github/awesome-copilot` 里有 `github-actions-hardening`、`github-actions-efficiency`、`create-github-action-workflow-specification`。

```bash
gh skill preview github/awesome-copilot github-actions-efficiency        # 先看，别直接装
gh skill install github/awesome-copilot github-actions-hardening --dir "C:\Users\<你>\.qoder-cn\skills"
```

⚠️ 必须带 `--dir`：`gh skill install --agent qoder` 会装到 `~/.qoder/skills`，而本机 Qoder CN 实际读的是 `~/.qoder-cn/skills`（gh 源码 `internal/skills/registry/registry.go` 里 qoder 的映射是 `.qoder/skills`），装错目录等于没装。

## 9. 完工标准（报告必须含，缺一项就不算完）

1. 一次真实 run 的 **URL + 结论**（绿/红），不接受"应该能跑"。
2. 用了哪个模板、改了哪几处、为什么。
3. §4 校验命令的输出原文。
4. 遗留项与**未能验证**的部分——明说，不掩饰。

## 10. 本机已知坑（实测，别再踩）

- `WebFetch` 抓 `docs.github.com` **必超时**（120s）→ 改用 `gh api repos/github/docs/contents/content/actions/<路径> -H "Accept: application/vnd.github.raw+json"` 读文档源码，URL 规则 = `https://docs.github.com/en/actions/` + 去掉前缀与 `.md`。只想核实某页是否存在时，`curl -sS -x http://127.0.0.1:7890 -o /dev/null -w "%{http_code}" <URL>` 可用（实测 200；注意目录 URL 会先 301 到无尾斜杠版）。
- `raw.githubusercontent.com` 直连下载超时 → 一律走 `gh api` 带 raw accept header。
- `gh api` 有限流，批量搜索/遍历省着用；撞到就减少调用，别重试轰炸。
- 路径含空格（`E:\Work\Qoder Projects\...`）必须加引号。
- 写文件用 Write 工具，别用 heredoc（Git Bash 会吃反斜杠）。
- 子智能体不做 git 提交；提交、push 归主线程。
- `gh skill list/install` **不跟随 Windows junction**：本机 `~/.qoder-cn/skills` 下的 junction 技能（github-cicd、smart-subagent、token-speed）在 `gh skill list --dir` 里全部不显示，而真实目录的技能正常显示；Qoder 自己能穿透 junction 加载。要对 junction 技能做 gh 操作，`--dir` 直接指到 E 盘真身目录。
- `gh skill list` 报的是**目录名**，Qoder 认的是 **frontmatter 里的 `name`**，两者必须一致才能顺利 `gh skill publish`（校验规则含「技能名须与目录名一致」）。本技能已对齐：目录 `github-cicd` = `name: github-cicd`。

## 资料

- `docs/official-docs-map.md` — 官方文档中文导航地图（按场景指路）
- `reference/gh-commands.md` — gh 命令速查：flag、JSON 字段、退出码（本机 gh 2.101.0 实测）
- `reference/troubleshooting.md` — 失败错因对照表与修法
- `reference/billing.md` — 什么免费、什么收费：套餐额度、标准 runner 单价、并发上限、reusable workflow 的计费归属、省钱清单
- `templates/base/` — 自己维护的 4 份骨架（ci / reusable-ci / caller-example / release）
- `templates/upstream/` — 官方 starter-workflows 存档 + `SOURCES.md`（来源路径与 sha）
