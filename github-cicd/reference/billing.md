# 计费：什么免费、什么收费（2026-09-27 核自官方文档）

一句话：**公开仓库用标准 runner = 免费**；私有仓库按套餐给月度免费额度，超出按分钟和存储计费；**larger runner 永远收费**。

## 1. 免费的部分

官方原文（`data/reusables/actions/actions-billing.md`）：标准 GitHub-hosted runner 在以下情形**免费**——

- **公开仓库**（public repositories）
- GitHub Pages 的构建
- Dependabot
- **self-hosted runner**（自己的机器，Actions 本身不收费，只花你自己的电和硬件）

所以本仓库（`oillvi/MySkills`，public）跑 CI 是零成本，这也是选它当靶场的原因。

## 2. 私有仓库：套餐包含额度

每月初分钟数归零重算；**分钟数记在仓库所有者账上，不是触发运行的人**。

| 额度 | Free | Pro | Team（组织免费版） | Team | Enterprise Cloud |
|---|---|---|---|---|---|
| 分钟数 / 月 | 2,000 | 3,000 | 2,000 | 3,000 | 50,000 |
| 存储 | 500 MB | 1 GB | 500 MB | 2 GB | 50 GB |

存储的三个要点：

- **artifact 存储与 GitHub Packages 共用同一份额度**（两者加起来不能超）。
- **cache 存储是独立额度：每仓库 10 GB**，不与 artifact / Packages 抢。
- 存储按**小时累计**计费（GB-Hours），不是按月底瞬时值。官方算例：存 10 GB 十天然后全删，账单仍按 2,400 GB-Hours 计。

**没绑支付方式时**：额度用完直接**阻断**（不允许超支）；larger runner 在绑卡前一律不可用。

## 3. 超额单价（标准 runner，按分钟）

| runner | Billing SKU | 每分钟 |
|---|---|---|
| Linux 1-core (x64) | `actions_linux_slim` | $0.002 |
| Linux 2-core (x64) | `actions_linux` | $0.006 |
| Linux 2-core (arm64) | `actions_linux_arm` | $0.005 |
| Windows 2-core (x64/arm64) | `actions_windows` / `actions_windows_arm` | $0.010 |
| macOS 3-或4-core (M1/Intel) | `actions_macos` | $0.062 |

官方算例：Team 套餐超额 5,000 分钟（3,000 Linux + 2,000 Windows）= $38（$18 + $20）。

存储超额：共享存储（artifact + Packages）**$0.25 / GB-月**；Actions cache **$0.07 / GB-月**；自定义镜像存储 **$0.07 / GB-月**。

> 旧文档里的「分钟倍率」（Windows 2×、macOS 10×）已被**按 SKU 直接标价**取代：`/billing/reference/actions-minute-multipliers` 现在是 `actions-runner-pricing` 页的 redirect_from 条目。看到老教程说倍率，按本页单价换算即可。

## 4. larger runner：永远收费

- **即使仓库是公开的、即使套餐还有额度，larger runner 也照收费**，包含分钟数不能用于它。
- 单价示例（x64）：Linux Advanced 2-core $0.006、Linux 4-core $0.012、8-core $0.022、16-core $0.042；Windows 4-core $0.022；macOS 12-core $0.077。GPU：Linux 4-core $0.052、Windows 4-core $0.102。
- 公开静态 IP 不额外收费。

## 5. 并发与规模上限（不是钱，但会卡住你）

| 套餐 | 标准 runner 总并发 job | 其中 macOS 上限 |
|---|---|---|
| Free | 20 | 5 |
| Pro | 40 | 5 |
| Team | 60 | 5 |
| Enterprise | 500 | 50 |

- job matrix 单次 workflow run 最多 **256 个 job**。
- 并发上限可以提工单让 GitHub Support 提高；**存储上限不能提**。
- Copilot code review 在私有仓库会**额外消耗 Actions 分钟数**（公开仓库仍然免费）。

## 6. 对「跨项目复用」的直接影响

官方明确规定（`content/actions/concepts/billing-and-usage.md` 的 "Billing for reusable workflows"）：

> 复用工作流时，**计费永远算在调用方（caller）**；GitHub-hosted runner 的分配也只按调用方的上下文评估，调用方**不能使用被调用仓库的 runner**。

含义：把中心流水线放在公开仓库 `oillvi/MySkills`，**不会**让私有项目白蹭免费分钟数——私有项目调用它，分钟数照样从私有项目所有者的额度里扣。想让私有项目也免费，只有把项目本身设为公开，或用 self-hosted runner。

## 6.5 实测记录（2026-09-27，本机）

私有靶场 `oillvi/cicd-sandbox`（`visibility=PRIVATE`）跨仓库调用公开中心的 reusable workflow，run 36328151540 成功，两个 job 各跑约 11 秒、`run_duration_ms: 28000`。

`GET /repos/{owner}/{repo}/actions/runs/{run_id}/timing` 返回 **`billable.UBUNTU.total_ms: 0`**（三个 job 的 `duration_ms` 全是 0）。**这个 0 不能作为「不扣分钟数」的证据**：可能是新版计费系统下该字段已不再填充，也可能是不足一分钟的舍入。

想确认自己账户真实消耗，两条路：

1. 网页：Settings → Billing and plans → **Usage this month**（最权威，只有账户本人能看）。
2. API：`gh api users/<用户名>/settings/billing/actions` 或 `.../billing/usage`——但**需要 `user` scope**，本机 token 只有 `gist, read:org, repo, workflow`，实测返回 404 并提示 `gh auth refresh -h github.com -s user`。

另外两个 Git Bash 坑：端点**不要写前导斜杠**（`gh api /users/...` 会被 MSYS 当路径改写成 `C:/Users/.../git/users/...`），或加 `MSYS_NO_PATHCONV=1`。

## 7. 省钱清单（按性价比排序）

1. `concurrency` + `cancel-in-progress`：连续 push 时取消旧跑。
2. `paths-ignore` 排除文档改动（本仓已生效：纯 `.md` 推送实测不触发 run）。
3. 依赖缓存：`setup-*` 的 `cache:` 或 `actions/cache`（cache 存储每仓库 10 GB 独立额度）。
4. 删掉不必要的 matrix 腿——每条腿都是完整一份分钟数。
5. 只在 Linux runner 上跑（$0.006/min，macOS 是它的 10 倍）。
6. `gh run rerun <id> --failed` 只重跑失败 job，不重跑整条流水线。
7. 用完 `gh cache delete` 清缓存；artifact 设 `retention-days`。
8. 别碰 larger runner，除非真的需要更多核。

## 出处

- [About billing for GitHub Actions](https://docs.github.com/en/actions/concepts/billing-and-usage)
- [Billing for GitHub Actions（含额度表、单价、算例）](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Product usage included with each plan](https://docs.github.com/en/billing/reference/product-usage-included)
- [Actions runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing)
- [Usage limits](https://docs.github.com/en/actions/reference/limits)
