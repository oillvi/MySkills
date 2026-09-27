# 上游模板存档来源

- 来源仓库：`actions/starter-workflows`
- 拉取方式：`gh api "repos/actions/starter-workflows/contents/<目录>/<文件名>"`（raw JSON，本地 base64 解码；未使用 curl 直连 raw.githubusercontent.com）
- 拉取日期：2026-09-27
- blob sha 可用 `gh api "repos/actions/starter-workflows/contents/<目录>/<文件名>" --jq '.sha'` 复核

| 本地文件 | 上游仓库路径 | blob sha | 拉取日期 |
|---|---|---|---|
| blank.yml | actions/starter-workflows:ci/blank.yml | 8decfee630352967ec4065ac71daecfa8c562eef | 2026-09-27 |
| python-package.yml | actions/starter-workflows:ci/python-package.yml | 19247ca7b7898dfcb315cb7dae8fbeb4e72d333c | 2026-09-27 |
| node.js.yml | actions/starter-workflows:ci/node.js.yml | d5ccc1494a2ffce6ef899211c3bcf19401fb8a13 | 2026-09-27 |
| docker-image.yml | actions/starter-workflows:ci/docker-image.yml | be757cca1e8d70a2f652c6f744d1702e64048de6 | 2026-09-27 |
| go.yml | actions/starter-workflows:ci/go.yml | 215474073318517ed321606f9638de0d7fa94f54 | 2026-09-27 |
| aws.yml | actions/starter-workflows:deployments/aws.yml | 3a1caa94adb59888ae22a46c6c2a702d93a9e62e | 2026-09-27 |
| stale.yml | actions/starter-workflows:automation/stale.yml | 1322eafd69729f4d12eb6886a36bddb16f6a6d83 | 2026-09-27 |
