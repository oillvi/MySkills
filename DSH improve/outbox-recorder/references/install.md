# 安装与运维手册

给人看的，不是给模型看的。模型只需要 `SKILL.md`。

## 1. 放哪

DSH 按固定优先级扫描技能根，`rank` 小的赢，重名的后者被忽略并只留一条日志：

| rank | 来源 | 路径 |
|---|---|---|
| 100 | project-dsh | `<项目根>/.dsh/skills` |
| 200 | project-agents | `<项目根>/.agents/skills` |
| 300 | custom | `Config.customSkillDirs` |
| 400 | user-dsh | `~/.dsh/skills`（或 `$DSH_HOME/skills`） |
| 500 | user-agents | `~/.agents/skills`（或 `$DSH_AGENTS_HOME/skills`） |
| 600 | bundled | `$DSH_BUNDLED_SKILL_DIR` |

「项目根」的定义是**向上找 `.git`**，找不到就退回当前工作目录。

只认两种布局，且**最深两段**：

```
<根>/outbox-recorder/SKILL.md     ← 目录式，本技能用这个
<根>/outbox-recorder.md           ← 扁平式
```

`scripts/`、`references/` 不会被当成技能，也不会自动加载；模型只会拿到一行「Base directory for this skill: …」的提示，然后按需 `read`。

按 Q1 的裁定，本技能与 `analog-*` **同一个根、平级**。三种做法都行：

- **符号链接**（推荐，与本机 `~/.dsh/skills -> MySkills` 的做法一致）：
  ```
  mklink /J "%USERPROFILE%\.dsh\skills\outbox-recorder" "<存放处>\outbox-recorder"
  ```
- **整体复制**：把 `outbox-recorder/` 整个拷进 `~/.dsh/skills/`
- **项目级**：拷进 `<项目根>/.dsh/skills/`，rank 100 最高，会遮蔽用户级同名技能

### 不要放进 analog-agents 仓库目录

两个实测过的坑（在本机用 `git check-ignore -v` 验的，不是推测）：

1. `analog-agents/.gitignore` 第 50 行是裸 `references/`。git 里不带斜杠的模式**匹配任意深度**，所以 `skills/<name>/references/` 会被整目录忽略——本技能的三份参考文档会静默地进不了版本库，重新 clone 就丢。
2. 顶层 `outbox/`、`skills/<name>/SKILL.md`、`skills/<name>/scripts/` **都不会**被那份 `.gitignore` 忽略，也就是会混进 arcadia-1 的仓库，你 pull 上游时可能冲突。
3. `skills/*/_local/` 会被忽略——这条本来对我们有利，但整目录重拷 arcadia-1 时 `_local/` 有被一起删掉的风险，而 `_local/` 里存着 `cell-map.yml`，删了就等于**占位符编号从头重排**，历史记录里的 `<cell_001>` 会对不上新记录。

所以：技能树独立存放，自带 `.gitignore`，自己 `git init`。

## 2. 首次运行

```
cd <技能目录>
python scripts/outbox.py init --project <项目名>
python scripts/outbox.py selftest
```

`init` 建骨架（`records/` 六个子目录、`drafts/`、`inbox/`、`_local/`、`MANIFEST.md`、`index.jsonl`、`.gitignore`），并写出 `_local/config.yml` 与 `_local/own-cells.txt` 的模板。

`selftest` 是 24 项内置用例，覆盖两道机、frontmatter 往返、字段校验、ID 与 slug、相似度。**装完先跑它**，绿了才说明搬运过程没把脚本弄坏。它不写任何记录，只读。

然后手工填两件事：

- `_local/config.yml`：`project`、`harness`、`desktop`、`arcadia1_sha`、`model`、以及 arcadia-1 的绝对路径（填 `ANALOG_AGENTS_ROOT`，或靠相对位置自动探测）。arcadia-1 的规矩是 `复现以 commit SHA 为准`，所以 `arcadia1_sha` 请填真 SHA。
- `_local/own-cells.txt`：本项目**自建**的 cell 名，一行一个，`#` 后面是注释。不在这份白名单里的 master 名，出现在代码围栏中会被替换成 `<cell_NNN>`，出现在散文里会被 R7 拒绝。

验证第一道机是否接上了 arcadia-1：

```
python scripts/sanitize_bridge.py --selftest
```

看第一行 `[info] tokens=N source=...`。`source=arcadia-1 @ <路径>` 才是满血；`built-in only` 说明没找到，去检查 `ANALOG_AGENTS_ROOT`。注意 arcadia-1 的 `_local/sanitize-map.yml` 是**每台机自己的、不进 git**，新机器上没有它是正常的，那时只有内置三条规则加你自己写的 `_local/outbox-map.yml`。

## 3. 确认 DSH 看得见它

在 DSH 里输入 `/outbox-recorder`。能展开正文就说明发现与解析都正常。

也可以让它自己触发：说一句「这个工具报错了，记一下」。模型会在 catalog 里按 `description` 匹配到它。

## 4. 携出流程

```
python scripts/outbox.py audit            # 必须全绿
python scripts/outbox.py bundle           # 产 outbox-<日期>.bundle
```

`bundle` 会：需要时 `git init` → 先跑一遍 `audit`（不过就拒绝打包，除非 `--force`）→ `git add -A` → 有改动就 commit → `git bundle create`。产出是**单个文件**，含全部历史，可校验、可增量续传。

`_local/`、`drafts/`、`inbox/_done/` 都在 `.gitignore` 里，**不会进 bundle**。带出去的只有记录、索引、清单和脚本。

外网侧解开：

```
git clone outbox-2026-09-28.bundle outbox-inbox
```

带一个文件出去比拷一个目录更不容易漏东西，这是 Q4 选 bundle 的理由。

## 5. 回执流程

外网侧对每条记录给结论，用**同一个脚本**（不用第二套工具）：

```
python scripts/outbox.py answer prob-0007 --status answered --note "设 simOutputFormat=psfxl"
python scripts/outbox.py answer prop-0001 --status approved --note "外网侧已建技能，下趟带进来"
python scripts/outbox.py answer wish-0002 --status wontfix --note "上游不支持"
```

每条命令产一个 `inbox/<ID>.md`。把这些文件带回内网，放进技能目录的 `inbox/`，然后：

```
python scripts/outbox.py sync-inbox
```

脚本改 `status`、在记录末尾追加 `## 外网回执`、把回执移进 `inbox/_done/`、重建索引。**模型不参与这一步**——已定稿记录的任何修改都由脚本做，这是 Q3 选 write-once 载体的直接后果。

状态词表：`pending-review` → `approved` / `rejected` / `answered` / `wontfix`。

## 6. 日常分诊

不必开一堆文件。`MANIFEST.md` 是脚本重建的一页清单，按 status 再按 project 分组，每行一个记录：ID / type / severity / project / recurrences / created / 标题。

```
python scripts/outbox.py list                          # 全部
python scripts/outbox.py list --status pending-review  # 待裁决
python scripts/outbox.py list --type skill-proposal    # 只看提案
```

`recurrences` 是提案去重的产物：同类提案再次出现时脚本不新建文件，而是给既有记录 +1 并追加一行时间戳。所以**这个数字就是「这件事又发生了一次」的计数器**，分诊时优先看数字大的。

## 7. 故障排查

| 症状 | 原因 | 怎么办 |
|---|---|---|
| `/outbox-recorder` 没反应，catalog 里也没有 | frontmatter 解析失败。DSH 对这类失败**只写一条 warn 日志然后静默跳过**，界面上看不出来 | 查 DSH 日志里的 `skill` warn。最常见三种：frontmatter 不是以整行 `---` 开合；`name` 不匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$`；写了 `disableModelInvocation` 这类驼峰别名（这个是**直接抛错**，不是忽略） |
| catalog 里出现了但少了内容 | `description` 超 500 字符被 catalog 截断 | 缩短 description，细节挪进正文 |
| 技能目录放对了还是不出现 | 距根超过两段，例如 `<根>/A/B/SKILL.md` | 上移一层 |
| 出现两份、行为不对 | 同名技能在多个根里都有，rank 小的赢，另一份被忽略 | 删掉低优先级那份 |
| `commit` 一直被 R7 拒 | 散文里反复出现某个 PDK 单元名 | 改成通用类别词（「一个低压 NMOS」），或把该名字加进 `_local/own-cells.txt`（仅当它确实是本项目自建的） |
| `commit` 报 `arcadia-1 sanitizer not found` | 第一道机降级了，只有内置三条规则 | 在 `_local/config.yml` 里填 `ANALOG_AGENTS_ROOT` 绝对路径 |
| `bundle` 拒绝打包 | `audit` 没过 | 看 audit 输出逐条修；确实要强行打包用 `--force`，但那样等于把未体检的记录带出内网 |
| `git` 相关命令报 127 | 内网机没装 git | `bundle` 用不了。退回手工拷 `records/` + `MANIFEST.md` + `index.jsonl` 三样，回执流程不变 |
| 控制台中文变问号 | Windows 控制台是 GBK | 脚本已 `reconfigure(encoding="utf-8")`，但控制台字体/代码页仍需 `chcp 65001` |

## 8. 红线政策

**严禁出现在任何记录里的东西**：PDK 的 model card 与器件模型参数、tech file、DRC/LVS 规则文件、库名/单元名/视图名、`Library name:` 与 `Cell name:` 这类抬头、真实绝对路径与用户名与服务器名。

**允许的**：本项目自己的网表片段（≤30 行，放在代码围栏里），其中的 PDK master 名由脚本自动占位化。

**允许且不应该被拦的**：点名工具与检查（「Calibre DRC 报了 12 条违例」）。这是描述问题，不是泄露数据。guard 对这类词只出 W2 告警。

责任划分：**脚本负责机械拦截，人负责携出前扫一眼 `audit` 的告警行。** 不要指望 27B 模型自己判断什么算敏感——那条路在设计阶段就被否掉了（Q2 选 (ii) 的理由）。

## 9. 版本与已知限制

- 目标运行时：DSH Desktop 2.0.15 / harness `@deepseek-ai/dsh` 0.1.7-rc.2。frontmatter 契约按这一版实测。若内网机是别的版本，先用 `/outbox-recorder` 确认能加载再继续。
- DSH 的 `write` 工具**没有 append 模式**，只能整文件替换。本技能的全部设计都绕开了它：模型只写新草稿，改既有文件一律由脚本做。
- DSH 的工具名是全小写（`read` `write` `edit` `bash` `glob` `grep`），与 Claude Code 的 `Read`/`Write`/`Edit` 不同。`SKILL.md` 里用的是小写。
- `str_replace_editor` 在 DSH 的 bundle 里存在但**没挂进 standard preset**，别依赖。
- 本技能写的是 `.md`，arcadia-1 的 hooks 只对 `.scs|.sp|.net` 与 `spectre|virtuoso-bridge` 触发，**不会校验它**。正确性全靠 `commit` 的两道机。
