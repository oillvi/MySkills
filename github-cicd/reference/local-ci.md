# 本地跑 CI 的四档路线（额度用完 / 想省钱 / 想快速迭代时看这里）

先回答「为什么 CI 默认在 GitHub 上跑」：CI 干的事确实就是执行代码，放到远端不是为了技术必需，而是为了四个本地很难同时拿到的性质——

1. **干净室**：每个 job 领一台全新 VM（单 CPU runner 是共享 VM 上的容器），杜绝「我机器上能跑」，也逼你把依赖声明写全。
2. **不可绕过**：远端 CI 才能当合并门禁（分支保护 + required checks）；本地检查永远可以被 `--no-verify` 跳掉。
3. **事件驱动 + 常开**：push / PR / tag / cron 全天候触发，你的机器可以关着。
4. **留痕与可见**：状态回写到 commit 和 PR，日志与 artifact 有留存、有可分享链接；团队看得到，单人也留下审计轨迹。
5. 附带两条：**密钥托管**在平台不下发到开发机；**matrix 并行 + 多 OS** 是笔记本给不了的。

对单人开发者，2/4/5 的价值下降，但 **1 和 3 依然成立**（干净环境、以及不用自己开机守着跑）。

## 四档路线（从轻到重，按需升级）

### 档 1：本地直接跑 CI 要跑的命令（零安装，首选）

不跑 workflow，只跑 workflow 里那几条命令。适合：命令本身是普通 CLI（pytest / ruff / npm test / go test）。

本机现状（2026-09-27 实测）：Python 3.12.10、pytest 9.1.1、ruff 0.16.9、node v24.18.0 **都在**，所以 `oillvi/MySkills` 的 CI 可以完整本地复现，耗时 0.6 秒：

```bash
python -m ruff check --select E9,F63,F7,F82 .
python -m pytest -q "smart-subagent/tools/test_probe.py" "smart-subagent/tools/test_tasktime.py" "token speed/tests/test_tokspeed.py"
```

想让它自动化：写成仓库里的一个脚本，或挂 pre-commit hook。
**局限（要认）**：本机不是干净环境（全局装过的包会掩盖「依赖没声明」）、可以被跳过、没有远端留痕。所以它替代的是**迭代速度**，不是**门禁**。

### 档 2：用 act 在本机跑同一份 workflow YAML（需要 Docker）

[nektos/act](https://github.com/nektos/act)（72k★，2026-08 仍在推，**社区项目、非 GitHub 官方**）用 Docker 容器在本机模拟 GitHub runner，跑的就是你仓库里那份 `.github/workflows/*.yml`。gh 扩展形式：`gh extension install nektos/gh-act`，然后 `gh act -j lint`。

价值：验证的是 **workflow 本身**（触发条件、job 依赖、表达式插值、action 版本），而不只是命令。反复调 YAML 时比「推一次等一次」快得多，也省分钟数。

**本机当前不具备**：`docker`、`act`、WSL 全部未安装（实测 `command not found`；`wsl -l -q` 报无已安装发行版）。要用得先装 Docker Desktop + WSL2（数 GB，Windows 上要吃虚拟化），值不值得看你是否频繁改 workflow。

### 档 3：self-hosted runner（远端体验 + 零分钟费用，但要机器常开）

把自己的机器注册成 runner，workflow 里写 `runs-on: self-hosted`。GitHub 仍负责触发、编排、记录、状态回写，**代码在你机器上执行**。

官方原文（`content/actions/concepts/runners/self-hosted-runners.md`）：

- "Are **free** to use with GitHub Actions, but you are responsible for the cost of maintaining your runner machines."
- "**Don't need to have a clean instance** for every job execution."（与 GitHub-hosted 的关键差别：不是每次全新环境，脏状态会残留）

⚠️ 官方安全警告（`data/reusables/actions/self-hosted-runner-security.md` 原文）：

> "We recommend that you **only use self-hosted runners with private repositories**. This is because forks of your public repository can potentially run dangerous code on your self-hosted runner machine by creating a pull request that executes the code in a workflow."

即：**公开仓库绝对不要挂自托管 runner**——陌生人 fork 后提个 PR，就能在你机器上执行任意代码。

本机额外顾虑：这台机器满载 95.9°C、风扇疑似间歇不升速，不适合当常驻 runner；且 runner 需要常驻进程 + 开机自启。

### 档 4：混合（推荐默认）

日常本地跑档 1（快、零成本）→ 推送后让 GitHub 跑一次远端 CI 当**不可绕过的留痕与门禁** → 只有在额度真耗尽、或要反复调 workflow 逻辑时，才动用档 2 / 档 3。

## 什么时候才会真的撞上额度

- **公开仓库用标准 runner 不限量免费**，不占额度。所以额度问题只影响**私有仓库**。
- 私有仓库额度是**账户级共享**（Free 2,000 分钟/月），按 **job 向上取整到整分钟**。
- 没绑支付方式时，额度用完直接**阻断**（不会偷偷扣钱）——这时档 1/2/3 就是唯一的继续方式。
- 参考量级：本机实测一次两 job 的小 CI ≈ 2 分钟 → 2,000 分钟 ≈ 每月一千次。单人开发通常用不完；用完了先怀疑 matrix 腿太多、job 拆太碎、缓存没配。

## 决策速查

| 你的处境 | 选哪档 |
|---|---|
| 只想快速迭代代码 | 档 1（本地直接跑命令） |
| 在反复调 workflow YAML 本身 | 档 2（act，先装 Docker） |
| 私有仓库额度耗尽且需要远端门禁 | 档 3（self-hosted，且仓库必须是私有） |
| 平时 | 档 4（本地跑 + 远端留痕） |
