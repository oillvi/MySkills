# GitHub Actions 官方文档导航地图（中文）

> 源数据：`github/docs` 仓库 `content/actions/` 目录树（全量路径清单见同目录 `_evidence-paths.txt`，247 个 markdown 文件）。
> URL 规则：`https://docs.github.com/en/actions/` + 去掉 `content/actions/` 前缀与 `.md` 后缀；`index.md` 映射为所在目录 URL。
> 本文件中每条 URL 都对应仓库中真实存在的文件，无虚构页面。

## 怎么用这份地图

- **第一次搭 CI**：先看 [快速入门](https://docs.github.com/en/actions/get-started/quickstart)，再读 [理解 GitHub Actions](https://docs.github.com/en/actions/get-started/understand-github-actions) 和 [工作流语法](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)，最后照抄一个 [工作流模板](https://docs.github.com/en/actions/how-tos/write-workflows/use-workflow-templates)。
- **排查失败**：入口是 [排障指南](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows)，配合 [工作流运行日志](https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs)、[查看运行历史](https://docs.github.com/en/actions/how-tos/monitor-workflows/view-workflow-run-history) 与 [调试日志开关](https://docs.github.com/en/actions/how-tos/monitor-workflows/enable-debug-logging)。
- **要做部署**：看 [部署总览](https://docs.github.com/en/actions/how-tos/deploy/) 与 [部署到环境](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/deploy-to-environment)，云上免密钥用 [OIDC 加固部署](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-cloud-providers)。
- **要跨项目复用**：读 [复用工作流配置](https://docs.github.com/en/actions/concepts/workflows-and-actions/reusing-workflow-configurations) 与 [复用自动化](https://docs.github.com/en/actions/how-tos/reuse-automations/)，组织级共享见 [与组织共享](https://docs.github.com/en/actions/how-tos/reuse-automations/share-with-your-organization)。
- **关心额度**：查 [计费与用量](https://docs.github.com/en/actions/concepts/billing-and-usage)、[各项限额](https://docs.github.com/en/actions/reference/limits)、[用量指标](https://docs.github.com/en/actions/concepts/metrics)。
- **选 runner**：对照 [GitHub 托管 runner](https://docs.github.com/en/actions/concepts/runners/github-hosted-runners) 与 [自托管 runner](https://docs.github.com/en/actions/concepts/runners/self-hosted-runners)。

---

## 入门与总览

- Actions 文档总目录，不确定从哪进就先点这里 — [GitHub Actions 文档首页](https://docs.github.com/en/actions/) （content/actions/index.md）
- 10 分钟跑通第一个工作流 — [快速入门](https://docs.github.com/en/actions/get-started/quickstart) （content/actions/get-started/quickstart.md）
- 建立整体心智模型：事件→作业→runner — [理解 GitHub Actions](https://docs.github.com/en/actions/get-started/understand-github-actions) （content/actions/get-started/understand-github-actions.md）
- 入门区总目录 — [入门与学习路径](https://docs.github.com/en/actions/get-started/) （content/actions/get-started/index.md）
- 用 Actions 搭第一条 CI 流水线 — [持续集成](https://docs.github.com/en/actions/get-started/continuous-integration) （content/actions/get-started/continuous-integration.md）
- 用 Actions 搭自动发布/部署流程 — [持续部署](https://docs.github.com/en/actions/get-started/continuous-deployment) （content/actions/get-started/continuous-deployment.md）
- 在纠结用 Action 还是 GitHub App 时看这页 — [Actions 对比 Apps](https://docs.github.com/en/actions/get-started/actions-vs-apps) （content/actions/get-started/actions-vs-apps.md）
- 概念区总目录 — [核心概念索引](https://docs.github.com/en/actions/concepts/) （content/actions/concepts/index.md）
- 快速把 Actions 接进现有仓库的示例工作流 — [创建示例工作流](https://docs.github.com/en/actions/tutorials/create-an-example-workflow) （content/actions/tutorials/create-an-example-workflow.md）

## 核心概念（工作流、上下文、表达式、变量、并发、缓存、部署环境、产物、自定义 action）

- 什么是工作流、YAML 放哪、怎么触发 — [工作流](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows) （content/actions/concepts/workflows-and-actions/workflows.md）
- 想知道 `${{ ... }}` 里能写什么对象（github、secrets、env…） — [上下文](https://docs.github.com/en/actions/concepts/workflows-and-actions/contexts) （content/actions/concepts/workflows-and-actions/contexts.md）
- 条件判断与函数（contains、startsWith…）怎么写 — [表达式](https://docs.github.com/en/actions/concepts/workflows-and-actions/expressions) （content/actions/concepts/workflows-and-actions/expressions.md）
- repository/organization/environment 变量的层级与优先级 — [变量](https://docs.github.com/en/actions/concepts/workflows-and-actions/variables) （content/actions/concepts/workflows-and-actions/variables.md）
- 同分支重复跑怎么互相排队/取消 — [并发控制](https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency) （content/actions/concepts/workflows-and-actions/concurrency.md）
- 依赖下载慢、想缓存 node_modules/pip 时看这页 — [依赖缓存](https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching) （content/actions/concepts/workflows-and-actions/dependency-caching.md）
- 环境与保护规则在工作流里怎么用 — [部署环境](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments) （content/actions/concepts/workflows-and-actions/deployment-environments.md）
- build 产物怎么上传、下游 job 怎么下载 — [工作流产物](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts) （content/actions/concepts/workflows-and-actions/workflow-artifacts.md）
- 想把自己重复的 YAML 抽成可复用单元 — [自定义 action](https://docs.github.com/en/actions/concepts/workflows-and-actions/custom-actions) （content/actions/concepts/workflows-and-actions/custom-actions.md）
- reusable workflows 的概念与代价 — [复用工作流配置](https://docs.github.com/en/actions/concepts/workflows-and-actions/reusing-workflow-configurations) （content/actions/concepts/workflows-and-actions/reusing-workflow-configurations.md）
- 工作流跑完怎么通知到 Slack/邮件 — [运行通知](https://docs.github.com/en/actions/concepts/workflows-and-actions/notifications-for-workflow-runs) （content/actions/concepts/workflows-and-actions/notifications-for-workflow-runs.md）
- 概念区：工作流与 action 分类入口 — [工作流与 Actions 概念](https://docs.github.com/en/actions/concepts/workflows-and-actions/) （content/actions/concepts/workflows-and-actions/index.md）

## 写工作流（触发事件、做什么、跑在哪、模板）

- 写工作流专题总入口 — [编写工作流](https://docs.github.com/en/actions/how-tos/write-workflows/) （content/actions/how-tos/write-workflows/index.md）
- 直接套官方模板起步 — [使用工作流模板](https://docs.github.com/en/actions/how-tos/write-workflows/use-workflow-templates) （content/actions/how-tos/write-workflows/use-workflow-templates.md）
- 决定「什么时候跑」的分组入口 — [选择工作流运行时机](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/) （content/actions/how-tos/write-workflows/choose-when-workflows-run/index.md）
- push/schedule/workflow_dispatch 等怎么配 — [触发工作流](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow) （content/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow.md）
- 用 if 只让某个分支/事件跑某 job — [用条件控制作业](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions) （content/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions.md）
- 同分支多次提交只保留最新一次运行 — [控制工作流并发](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency) （content/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency.md）
- 决定「做什么」的分组入口 — [选择工作流做什么](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/) （content/actions/how-tos/write-workflows/choose-what-workflows-do/index.md）
- 在步骤里写 shell 命令的注意事项 — [添加脚本](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/add-scripts) （content/actions/how-tos/write-workflows/choose-what-workflows-do/add-scripts.md）
- 挑选/修改社区 action 的正确姿势 — [查找并自定义 Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/find-and-customize-actions) （content/actions/how-tos/write-workflows/choose-what-workflows-do/find-and-customize-actions.md）
- job 的写法、needs、多 job 编排 — [使用作业](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs) （content/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs.md）
- 步骤间怎么传值 — [传递作业输出](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/pass-job-outputs) （content/actions/how-tos/write-workflows/choose-what-workflows-do/pass-job-outputs.md）
- matrix、fail-fast、include/exclude — [作业的多种运行变体](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations) （content/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations.md）
- 给 job 设置默认 shell/超时等 — [为作业设置默认值](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/set-default-values-for-jobs) （content/actions/how-tos/write-workflows/choose-what-workflows-do/set-default-values-for-jobs.md）
- 在工作流里用 gh CLI 干活 — [使用 GitHub CLI](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-github-cli) （content/actions/how-tos/write-workflows/choose-what-workflows-do/use-github-cli.md）
- 密钥怎么定义、怎么引用 — [使用 Secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets) （content/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets.md）
- 工作流/作业里怎么用变量 — [使用变量](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables) （content/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables.md）
- 把发布动作指向某个 environment 并走审批 — [部署到环境](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/deploy-to-environment) （content/actions/how-tos/write-workflows/choose-what-workflows-do/deploy-to-environment.md）
- 决定「跑在哪」的分组入口 — [选择作业运行位置](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/) （content/actions/how-tos/write-workflows/choose-where-workflows-run/index.md）
- runs-on 怎么选 labels/runner 组 — [为作业选择 runner](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job) （content/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job.md）
- 需要 Postgres/Redis 时把服务跑在容器里 — [在容器中运行作业](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/run-jobs-in-a-container) （content/actions/how-tos/write-workflows/choose-where-workflows-run/run-jobs-in-a-container.md）

## 部署

- 部署专题总入口 — [部署](https://docs.github.com/en/actions/how-tos/deploy/) （content/actions/how-tos/deploy/index.md）
- 配置与管理部署的分组入口 — [配置与管理部署](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/) （content/actions/how-tos/deploy/configure-and-manage-deployments/index.md）
- 建 environment、设必需审批/等待计时 — [管理环境](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments) （content/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments.md）
- 限制谁能发起部署 — [控制部署](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments) （content/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments.md）
- 审批人视角怎么批准/拒绝部署 — [审核部署](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments) （content/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments.md）
- 回看每次部署是谁在何时做的 — [查看部署历史](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/view-deployment-history) （content/actions/how-tos/deploy/configure-and-manage-deployments/view-deployment-history.md）
- 写自定义的部署保护规则 — [创建自定义保护规则](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/create-custom-protection-rules) （content/actions/how-tos/deploy/configure-and-manage-deployments/create-custom-protection-rules.md）
- 配置已装的保护规则应用 — [配置自定义保护规则](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/configure-custom-protection-rules) （content/actions/how-tos/deploy/configure-and-manage-deployments/configure-custom-protection-rules.md）
- 部署到 AWS/Azure/GCP 等平台的分组入口 — [部署到第三方平台](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/) （content/actions/how-tos/deploy/deploy-to-third-party-platforms/index.md）
- Node.js 应用发布到 Azure App Service — [Node.js 部署到 Azure](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/nodejs-to-azure-app-service) （content/actions/how-tos/deploy/deploy-to-third-party-platforms/nodejs-to-azure-app-service.md）
- Python 应用发布到 Azure App Service — [Python 部署到 Azure](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/python-to-azure-app-service) （content/actions/how-tos/deploy/deploy-to-third-party-platforms/python-to-azure-app-service.md）
- 构建镜像推到 registry 并部署 — [Docker 部署到 Azure App Service](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/docker-to-azure-app-service) （content/actions/how-tos/deploy/deploy-to-third-party-platforms/docker-to-azure-app-service.md）
- 静态站点一键发布 — [Azure Static Web Apps 部署](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/azure-static-web-app) （content/actions/how-tos/deploy/deploy-to-third-party-platforms/azure-static-web-app.md）
- 发布到 AKS 集群 — [部署到 Azure Kubernetes Service](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/azure-kubernetes-service) （content/actions/how-tos/deploy/deploy-to-third-party-platforms/azure-kubernetes-service.md）
- 发布到 GKE 集群 — [部署到 Google Kubernetes Engine](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/google-kubernetes-engine) （content/actions/how-tos/deploy/deploy-to-third-party-platforms/google-kubernetes-engine.md）
- 发布到 Amazon ECS — [部署到 Amazon ECS](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/amazon-elastic-container-service) （content/actions/how-tos/deploy/deploy-to-third-party-platforms/amazon-elastic-container-service.md）
- 给 macOS 应用签名公证 — [签名 Xcode 应用](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications) （content/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications.md）

## 运维工作流运行（重跑、取消、下载产物、缓存管理、手动触发、fork 审批、跳过运行、排障）

- 运行管理专题总入口 — [管理工作流运行](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/) （content/actions/how-tos/manage-workflow-runs/index.md）
- 失败后重跑单个 job 或整条流水线 — [重跑工作流与作业](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs) （content/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs.md）
- 跑错分支/误触发时立即止损 — [取消工作流运行](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/cancel-a-workflow-run) （content/actions/how-tos/manage-workflow-runs/cancel-a-workflow-run.md）
- 下载某次运行产出的构建产物 — [下载工作流产物](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts) （content/actions/how-tos/manage-workflow-runs/download-workflow-artifacts.md）
- 清理过期产物释放配额 — [删除工作流产物](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/remove-workflow-artifacts) （content/actions/how-tos/manage-workflow-runs/remove-workflow-artifacts.md）
- 查看/删除某次运行的缓存条目 — [管理缓存](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manage-caches) （content/actions/how-tos/manage-workflow-runs/manage-caches.md）
- 想给带 inputs 的流水线手工发一发 — [手动运行工作流](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow) （content/actions/how-tos/manage-workflow-runs/manually-run-a-workflow.md）
- PR 来自 fork 时维护者怎么放行 — [批准来自 fork 的运行](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/approve-runs-from-forks) （content/actions/how-tos/manage-workflow-runs/approve-runs-from-forks.md）
- 提交信息加 [skip] 免跑 — [跳过工作流运行](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs) （content/actions/how-tos/manage-workflow-runs/skip-workflow-runs.md）
- 暂时停用某条 YAML（如连红的流水线） — [禁用与启用工作流](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows) （content/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows.md）
- 归档某条运行记录 — [删除工作流运行](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/delete-a-workflow-run) （content/actions/how-tos/manage-workflow-runs/delete-a-workflow-run.md）
- 监控专题总入口 — [监控工作流](https://docs.github.com/en/actions/how-tos/monitor-workflows/) （content/actions/how-tos/monitor-workflows/index.md）
- 翻历史找哪次提交开始变红 — [查看工作流运行历史](https://docs.github.com/en/actions/how-tos/monitor-workflows/view-workflow-run-history) （content/actions/how-tos/monitor-workflows/view-workflow-run-history.md）
- 读失败 job 的完整日志 — [使用工作流运行日志](https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs) （content/actions/how-tos/monitor-workflows/use-workflow-run-logs.md）
- 需要更细的调试输出时打开 debug — [启用调试日志](https://docs.github.com/en/actions/how-tos/monitor-workflows/enable-debug-logging) （content/actions/how-tos/monitor-workflows/enable-debug-logging.md）
- 可视化 job 依赖与运行时长 — [使用可视化图表](https://docs.github.com/en/actions/how-tos/monitor-workflows/use-the-visualization-graph) （content/actions/how-tos/monitor-workflows/use-the-visualization-graph.md）
- 想看某步骤 if 为什么没进/进了 — [查看作业条件日志](https://docs.github.com/en/actions/how-tos/monitor-workflows/view-job-condition-logs) （content/actions/how-tos/monitor-workflows/view-job-condition-logs.md）
- 找最慢的 job 做优化 — [查看作业执行时长](https://docs.github.com/en/actions/how-tos/monitor-workflows/view-job-execution-time) （content/actions/how-tos/monitor-workflows/view-job-execution-time.md）
- README 上挂一个 CI 状态徽章 — [添加状态徽章](https://docs.github.com/en/actions/how-tos/monitor-workflows/add-a-status-badge) （content/actions/how-tos/monitor-workflows/add-a-status-badge.md）
- 通用排障入口（报错先查这里） — [排障工作流](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows) （content/actions/how-tos/troubleshoot-workflows.md）
- 官方支持渠道与社区入口 — [获取支持](https://docs.github.com/en/actions/how-tos/get-support) （content/actions/how-tos/get-support.md）
- how-tos 区总目录 — [操作指南索引](https://docs.github.com/en/actions/how-tos/) （content/actions/how-tos/index.md）

## 复用与通用化（reusable workflows、创建模板、组织内共享、跨私有仓库共享）

- 复用专题总入口 — [复用自动化](https://docs.github.com/en/actions/how-tos/reuse-automations/) （content/actions/how-tos/reuse-automations/index.md）
- 把一条流水线改造成可被 call 的 reusable workflow — [复用工作流](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows) （content/actions/how-tos/reuse-automations/reuse-workflows.md）
- 把自家 YAML 做成新建文件时可选的模板 — [创建工作流模板](https://docs.github.com/en/actions/how-tos/reuse-automations/create-workflow-templates) （content/actions/how-tos/reuse-automations/create-workflow-templates.md）
- 组织内多个仓库共用一套 CI — [与组织共享](https://docs.github.com/en/actions/how-tos/reuse-automations/share-with-your-organization) （content/actions/how-tos/reuse-automations/share-with-your-organization.md）
- 企业级统一治理与共享 — [与企业共享](https://docs.github.com/en/actions/how-tos/reuse-automations/share-with-your-enterprise) （content/actions/how-tos/reuse-automations/share-with-your-enterprise.md）
- 私有仓库之间怎么互 call 而不公开 — [跨私有仓库共享](https://docs.github.com/en/actions/how-tos/reuse-automations/share-across-private-repositories) （content/actions/how-tos/reuse-automations/share-across-private-repositories.md）
- 自己写 action 的发布/维护手册 — [创建与发布 Actions](https://docs.github.com/en/actions/how-tos/create-and-publish-actions/) （content/actions/how-tos/create-and-publish-actions/index.md）
- 给 action 写合理的退出码 — [设置退出码](https://docs.github.com/en/actions/how-tos/create-and-publish-actions/set-exit-codes) （content/actions/how-tos/create-and-publish-actions/set-exit-codes.md）
- 用不可变 release/tag 管理 action 版本 — [不可变发布与标签](https://docs.github.com/en/actions/how-tos/create-and-publish-actions/using-immutable-releases-and-tags-to-manage-your-actions-releases) （content/actions/how-tos/create-and-publish-actions/using-immutable-releases-and-tags-to-manage-your-actions-releases.md）
- action 上架 Marketplace — [发布到 GitHub Marketplace](https://docs.github.com/en/actions/how-tos/create-and-publish-actions/publish-in-github-marketplace) （content/actions/how-tos/create-and-publish-actions/publish-in-github-marketplace.md）

## 安全（部署加固、产物证明、密钥）

- 安全区总入口 — [保护你的工作](https://docs.github.com/en/actions/how-tos/secure-your-work/) （content/actions/how-tos/secure-your-work/index.md）
- 用 OIDC 免静态密钥访问云 — [加固部署总览](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/) （content/actions/how-tos/secure-your-work/security-harden-deployments/index.md）
- 各云厂商 OIDC 的通用接入方式 — [云提供商 OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-cloud-providers) （content/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-cloud-providers.md）
- AWS IAM 角色联合认证 — [在 AWS 使用 OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws) （content/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws.md）
- Azure 联合凭据 — [在 Azure 使用 OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure) （content/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure.md）
- GCP Workload Identity — [在 GCP 使用 OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-google-cloud-platform) （content/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-google-cloud-platform.md）
- Vault 动态秘钥 — [在 HashiCorp Vault 使用 OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-hashicorp-vault) （content/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-hashicorp-vault.md）
- OIDC 跨 reusable workflow 传递 — [OIDC 与可复用工作流](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-with-reusable-workflows) （content/actions/how-tos/secure-your-work/security-harden-deployments/oidc-with-reusable-workflows.md）
- 产物证明专题入口 — [使用产物证明](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/) （content/actions/how-tos/secure-your-work/use-artifact-attestations/index.md）
- 给构建产物生成 provenance 证明 — [生成产物证明](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations) （content/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations.md）
- 消费端强制校验证明 — [强制校验证明](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/enforce-artifact-attestations) （content/actions/how-tos/secure-your-work/use-artifact-attestations/enforce-artifact-attestations.md）
- 无网环境离线验证 — [离线验证证明](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/verify-attestations-offline) （content/actions/how-tos/secure-your-work/use-artifact-attestations/verify-attestations-offline.md）
- 密钥概念与最佳实践 — [Secrets](https://docs.github.com/en/actions/concepts/security/secrets) （content/actions/concepts/security/secrets.md）
- GITHUB_TOKEN 的权限边界 — [github_token](https://docs.github.com/en/actions/concepts/security/github_token) （content/actions/concepts/security/github_token.md）
- OIDC 概念与 claims 结构 — [OpenID Connect](https://docs.github.com/en/actions/concepts/security/openid-connect) （content/actions/concepts/security/openid-connect.md）
- 脚本注入攻击的识别与防御 — [脚本注入](https://docs.github.com/en/actions/concepts/security/script-injections) （content/actions/concepts/security/script-injections.md）
- runner 被入侵后怎么止损 — [被入侵的 runner](https://docs.github.com/en/actions/concepts/security/compromised-runners) （content/actions/concepts/security/compromised-runners.md）
- 概念区：安全分组入口 — [安全概念](https://docs.github.com/en/actions/concepts/security/) （content/actions/concepts/security/index.md）
- 仓库/组织级 Actions 策略限制 — [Actions 策略](https://docs.github.com/en/actions/concepts/about-actions-policies) （content/actions/concepts/about-actions-policies.md）
- 参考区：安全加固总纲 — [安全使用指南](https://docs.github.com/en/actions/reference/security/secure-use) （content/actions/reference/security/secure-use.md）
- 用 pull_request_target 的正确姿势与雷区 — [安全使用 pull_request_target](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target) （content/actions/reference/security/securely-using-pull_request_target.md）

## 额度与限额（billing-and-usage、limits、metrics）

- 分钟数/存储怎么计费 — [计费与用量](https://docs.github.com/en/actions/concepts/billing-and-usage) （content/actions/concepts/billing-and-usage.md）
- 并发 job 数、artifact 大小等硬上限 — [限额](https://docs.github.com/en/actions/reference/limits) （content/actions/reference/limits.md）
- 看本组织的用量指标 — [用量指标](https://docs.github.com/en/actions/concepts/metrics) （content/actions/concepts/metrics.md）
- 管理员查看组织级运行指标 — [查看指标](https://docs.github.com/en/actions/how-tos/administer/view-metrics) （content/actions/how-tos/administer/view-metrics.md）
- 管理员控制工作流执行策略 — [控制工作流执行](https://docs.github.com/en/actions/how-tos/administer/control-workflow-execution) （content/actions/how-tos/administer/control-workflow-execution.md）
- 管理员专题入口 — [管理 Actions](https://docs.github.com/en/actions/how-tos/administer/) （content/actions/how-tos/administer/index.md）

## 参考（workflow 语法、触发事件、runner、上下文）

- 参考区总目录 — [参考手册](https://docs.github.com/en/actions/reference/) （content/actions/reference/index.md）
- 写 YAML 时逐字段对照的语法全书 — [工作流语法](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) （content/actions/reference/workflows-and-actions/workflow-syntax.md）
- 查某个事件的触发条件与 payload — [触发工作流的事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) （content/actions/reference/workflows-and-actions/events-that-trigger-workflows.md）
- 可用上下文对象的完整字段表 — [上下文](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts) （content/actions/reference/workflows-and-actions/contexts.md）
- 表达式语法与运算符参考 — [表达式](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions) （content/actions/reference/workflows-and-actions/expressions.md）
- 默认/密钥/作用域变量清单 — [变量](https://docs.github.com/en/actions/reference/workflows-and-actions/variables) （content/actions/reference/workflows-and-actions/variables.md）
- set-output、::error:: 等运行时命令 — [工作流命令](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands) （content/actions/reference/workflows-and-actions/workflow-commands.md）
- deployment/environment 相关参考 — [部署与环境](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments) （content/actions/reference/workflows-and-actions/deployments-and-environments.md）
- cache 的作用域与键规则参考 — [依赖缓存](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching) （content/actions/reference/workflows-and-actions/dependency-caching.md）
- reusable workflow 的 on/workflow_call 语法 — [复用工作流配置](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations) （content/actions/reference/workflows-and-actions/reusing-workflow-configurations.md）
- action.yml 的 metadata 字段参考 — [元数据语法](https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax) （content/actions/reference/workflows-and-actions/metadata-syntax.md）
- Docker 容器 action 的额外支持 — [Dockerfile 支持](https://docs.github.com/en/actions/reference/workflows-and-actions/dockerfile-support) （content/actions/reference/workflows-and-actions/dockerfile-support.md）
- cancel-in-progress 等取消语义 — [工作流取消](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-cancellation) （content/actions/reference/workflows-and-actions/workflow-cancellation.md）
- 参考区：工作流与 action 分组入口 — [工作流与 Actions 参考](https://docs.github.com/en/actions/reference/workflows-and-actions/) （content/actions/reference/workflows-and-actions/index.md）
- runner 概念与选型总览 — [Runners](https://docs.github.com/en/actions/reference/runners/) （content/actions/reference/runners/index.md）
- 托管 runner 规格、镜像、预装软件 — [GitHub 托管 runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) （content/actions/reference/runners/github-hosted-runners.md）
- 自托管 runner 参考 — [自托管 runner](https://docs.github.com/en/actions/reference/runners/self-hosted-runners) （content/actions/reference/runners/self-hosted-runners.md）
- 大型 runner 的规格与限制 — [大型 runner](https://docs.github.com/en/actions/reference/runners/larger-runners) （content/actions/reference/runners/larger-runners.md）
- OIDC token 请求参考 — [OIDC](https://docs.github.com/en/actions/reference/security/oidc) （content/actions/reference/security/oidc.md）
- Secrets 参考 — [Secrets](https://docs.github.com/en/actions/reference/security/secrets) （content/actions/reference/security/secrets.md）
- 参考区：安全分组入口 — [安全参考](https://docs.github.com/en/actions/reference/security/) （content/actions/reference/security/index.md）
- 托管 runner 概念（区别于自托管） — [GitHub 托管 runner 概念](https://docs.github.com/en/actions/concepts/runners/github-hosted-runners) （content/actions/concepts/runners/github-hosted-runners.md）
- 自己机器当 runner 的概念 — [自托管 runner 概念](https://docs.github.com/en/actions/concepts/runners/self-hosted-runners) （content/actions/concepts/runners/self-hosted-runners.md）
- runner 组做权限隔离 — [Runner 组](https://docs.github.com/en/actions/concepts/runners/runner-groups) （content/actions/concepts/runners/runner-groups.md）
- 私有网络连通性方案 — [私有网络](https://docs.github.com/en/actions/concepts/runners/private-networking) （content/actions/concepts/runners/private-networking.md）
- 用 ARC 在 K8s 上弹性跑 runner — [Actions Runner Controller](https://docs.github.com/en/actions/concepts/runners/actions-runner-controller) （content/actions/concepts/runners/actions-runner-controller.md）

## 教程（构建与测试、发布包、github_token 认证、存取数据、迁移到 Actions、agentic workflows）

- 教程区总目录 — [教程](https://docs.github.com/en/actions/tutorials/) （content/actions/tutorials/index.md）
- 各语言构建测试教程入口 — [构建与测试代码](https://docs.github.com/en/actions/tutorials/build-and-test-code/) （content/actions/tutorials/build-and-test-code/index.md）
- Go 项目的 CI — [Go 构建与测试](https://docs.github.com/en/actions/tutorials/build-and-test-code/go) （content/actions/tutorials/build-and-test-code/go.md）
- Node.js 项目的 CI — [Node.js 构建与测试](https://docs.github.com/en/actions/tutorials/build-and-test-code/nodejs) （content/actions/tutorials/build-and-test-code/nodejs.md）
- Python 项目的 CI — [Python 构建与测试](https://docs.github.com/en/actions/tutorials/build-and-test-code/python) （content/actions/tutorials/build-and-test-code/python.md）
- Java（Maven）项目的 CI — [Java with Maven](https://docs.github.com/en/actions/tutorials/build-and-test-code/java-with-maven) （content/actions/tutorials/build-and-test-code/java-with-maven.md）
- Rust 项目的 CI — [Rust 构建与测试](https://docs.github.com/en/actions/tutorials/build-and-test-code/rust) （content/actions/tutorials/build-and-test-code/rust.md）
- 用 GITHUB_TOKEN 做认证的完整说明 — [使用 github_token 认证](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token) （content/actions/tutorials/authenticate-with-github_token.md）
- 作业间/跨运行存取数据的做法 — [存储与共享数据](https://docs.github.com/en/actions/tutorials/store-and-share-data) （content/actions/tutorials/store-and-share-data.md）
- 发布制品教程入口 — [发布包](https://docs.github.com/en/actions/tutorials/publish-packages/) （content/actions/tutorials/publish-packages/index.md）
- CI 里构建推送 Docker 镜像 — [发布 Docker 镜像](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images) （content/actions/tutorials/publish-packages/publish-docker-images.md）
- CI 里发布 npm 包 — [发布 Node.js 包](https://docs.github.com/en/actions/tutorials/publish-packages/publish-nodejs-packages) （content/actions/tutorials/publish-packages/publish-nodejs-packages.md）
- 迁移到 Actions 总入口 — [迁移到 GitHub Actions](https://docs.github.com/en/actions/tutorials/migrate-to-github-actions/) （content/actions/tutorials/migrate-to-github-actions/index.md）
- 用 GitHub Actions Importer 自动迁移 — [使用 GitHub Actions Importer](https://docs.github.com/en/actions/tutorials/migrate-to-github-actions/automated-migrations/use-github-actions-importer) （content/actions/tutorials/migrate-to-github-actions/automated-migrations/use-github-actions-importer.md）
- 从 Jenkins 手动迁移 — [从 Jenkins 迁移](https://docs.github.com/en/actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-jenkins) （content/actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-jenkins.md）
- 从 GitLab CI 手动迁移 — [从 GitLab CI/CD 迁移](https://docs.github.com/en/actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-gitlab-cicd) （content/actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-gitlab-cicd.md）
- 从 CircleCI 手动迁移 — [从 CircleCI 迁移](https://docs.github.com/en/actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-circleci) （content/actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-circleci.md）
- 把 CI 迁到自建 runner — [迁移到 GitHub Runner](https://docs.github.com/en/actions/tutorials/migrate-to-github-runners) （content/actions/tutorials/migrate-to-github-runners.md）
- 用 LLM 在 Actions 里跑 agentic 任务 — [开发 Agentic 工作流](https://docs.github.com/en/actions/tutorials/develop-agentic-workflows-in-github-actions) （content/actions/tutorials/develop-agentic-workflows-in-github-actions.md）
- 自己造 action 的三个入门教程 — [创建 Actions](https://docs.github.com/en/actions/tutorials/create-actions/) （content/actions/tutorials/create-actions/index.md）
- 把多个步骤封装成 composite action — [创建复合 action](https://docs.github.com/en/actions/tutorials/create-actions/create-a-composite-action) （content/actions/tutorials/create-actions/create-a-composite-action.md）
- 用 JavaScript 写 action — [创建 JavaScript action](https://docs.github.com/en/actions/tutorials/create-actions/create-a-javascript-action) （content/actions/tutorials/create-actions/create-a-javascript-action.md）
- 服务容器（Postgres）教程 — [创建 PostgreSQL 服务容器](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers) （content/actions/tutorials/use-containerized-services/create-postgresql-service-containers.md）
- 服务容器（Redis）教程 — [创建 Redis 服务容器](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-redis-service-containers) （content/actions/tutorials/use-containerized-services/create-redis-service-containers.md）
- 用 Docker 容器 action — [创建 Docker 容器 action](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-a-docker-container-action) （content/actions/tutorials/use-containerized-services/create-a-docker-container-action.md）
- ARC 上手教程 — [ARC 入门](https://docs.github.com/en/actions/tutorials/use-actions-runner-controller/get-started) （content/actions/tutorials/use-actions-runner-controller/get-started.md）
- ARC 排障 — [ARC 排障](https://docs.github.com/en/actions/tutorials/use-actions-runner-controller/troubleshoot) （content/actions/tutorials/use-actions-runner-controller/troubleshoot.md）
- 用 GitHub CLI 快速建 issue/PR 的自动化 — [管理工作：加标签](https://docs.github.com/en/actions/tutorials/manage-your-work/add-labels-to-issues) （content/actions/tutorials/manage-your-work/add-labels-to-issues.md）
- 自动关闭长期无响应 issue — [关闭不活跃的 issue](https://docs.github.com/en/actions/tutorials/manage-your-work/close-inactive-issues) （content/actions/tutorials/manage-your-work/close-inactive-issues.md）

