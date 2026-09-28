# 拦截规则

`commit` 跑两道机。第一道是替换（复用 arcadia-1 的 token map），第二道是检测（`scripts/guard.py`）。这份文件是每条规则的原文、理由、以及怎么改才能过。

**总原则：拿不准就脱敏。** 误拦的代价是模型多改一轮；漏拦的代价是 PDK 数据出了内网，不可回收。

## 第一道机：token 替换

`scripts/sanitize_bridge.py`，只替换不拒绝。

| 来源 | 内容 |
|---|---|
| 内置 | `/home/` → `<userhome>/`、`/opt/` → `<vendorpath>/`、`/eda/` → `<edapath>/` |
| arcadia-1 | `<analog-agents>/_local/sanitize-map.yml`，通过 import 它的 `load_token_map` 读取 |
| 本技能 | `_local/outbox-map.yml`，扁平 `src: dst`，优先级最高 |

替换按 **key 长度倒序**，所以短 token 不会吃掉长 token 的一部分（arcadia-1 用的同一条规矩）。

定位 arcadia-1 的顺序：环境变量 `ANALOG_AGENTS_ROOT` → `ARCADIA1_ROOT` → `_local/config.yml` 里的同名键 → 相对路径探测 `../analog-agents`、`../../analog-agents`、`../../arcadia-1/analog-agents`、`../arcadia-1/analog-agents`。

**降级路径（都不崩，只打一行 `[warn]`）**：找不到 arcadia-1 → 只用内置规则；没有 PyYAML → map 退化成 `key: value` 行解析；map 文件不存在 → 空表。

降级是刻意的：这台机器上崩一次等于静默关掉脱敏，那比规则少几条严重得多。所以每次 `commit` 都会打印 `[gate1] tokens=N source=...`，人一眼能看出第一道机是不是满血。

## 第二道机：结构检测

### 拒绝类

| 规则 | 匹配什么 | 为什么 | 怎么改 |
|---|---|---|---|
| **R0** | 残留的 `{{...}}` | 模板占位符没填完就定稿，说明这条记录没写完 | 把每个 `{{...}}` 换成真实内容 |
| **R1** | SPICE/Spectre 的 `model` 卡或 `subckt` 定义体；`library` / `section` / `endsection` 块；`simulator lang=` | 这些就是库数据本体 | 整行删掉。要描述现象就写「模型卡加载失败」，不要贴卡片内容 |
| **R2** | `include` / `.include` / `ahdl_include` 后面跟真实路径 | include 路径直接暴露 PDK 装在哪 | 写成 `include "/path/to/pdk/models/spectre/tt.scs"`。arcadia-1 的设计网表本来就用这个占位形式 |
| **R3** | 库/规则/版图文件名：`*.oa` `*.lib` `*.cdl` `*.tf` `*.svrf` `*.drcs` `*.cdb` `*.gds` `*.gdsii`；以及 `techfile` / `rule deck` / `layermap` / `liberty` / `openaccess` / `stream out` 后面跟文件名 | 文件名本身就是资产清单 | 写「规则文件加载失败」，不要写文件名 |
| **R4** | `Library name:` / `Cell name:` / `libId` / `cellView` / `view name:` 后面跟非占位值 | arcadia-1 `AGENTS.md` 亲自点名的敏感「马脚」，出现在网表抬头里 | 换成 `<library>` / `<cell>`，或者整行删掉 |
| **R5** | 绝对路径与用户名：`X:\`、`/home/`、`/opt/`、`/eda/`、`/Users/`、`/mnt/`、`/project/`、UNC `\\host\share` | 暴露机器布局、用户名、服务器名 | 用 `<project>/tools/xxx.py` 这类占位写法 |
| **R7** | **正文散文里**出现像 PDK master 名的词：含数字、小写、以器件族前缀开头（见下） | 选项 (ii) 的裁定：master 名也算库数据 | 改成通用类别词，例如「一个低压 NMOS」；如果那确实是本项目自建的单元，把名字加进 `_local/own-cells.txt` |

### 自动替换类

| 规则 | 匹配什么 | 处置 |
|---|---|---|
| **R6** | **代码围栏内**的 master/cell 名：Spectre 实例行的 `inst (nodes) master` 位置、SPICE 实例行的 master 位置、以及任何像 PDK 单元名的 token | 换成 `<cell_NNN>`，对应关系追加进 `_local/cell-map.yml` |

R6 用替换而不是拒绝，是为了不打断流程。占位符**跨记录稳定**：同一个真名永远换到同一个 `<cell_NNN>`，按首次出现的顺序编号。所以外网侧能把不同记录里的 `<cell_001>` 认成同一个器件。

`_local/cell-map.yml` 和 `_local/own-cells.txt` 都不进 git、不进 bundle、永不外携。

### 告警类（不拦）

| 规则 | 触发 | 为什么只告警 |
|---|---|---|
| **W1** | 正文超 200 行；代码证据超 30 行 | 长度问题不是泄密问题 |
| **W2** | 出现 `techfile` `tech file` `liberty` `rule deck` `layermap` `assura` `diva` `calibre` `antenna` `drc` `lvs` `openaccess` `gdsii` `stream out` `cdl` 这些词 | **点名工具和一个检查是合法的问题描述**，不含数据。「Calibre DRC 报了 12 条 metal1 间距违例」正是要记的东西，拦掉它这个技能就没用了。所以只提醒人在携出前扫一眼这些行 |

> R3 曾经按词汇拦截，结果既拦掉了模板自己的说明文字，也会拦掉所有诚实的 DRC/LVS 故障报告。改成「**拦数据，不拦词汇**」：只有文件名和被点名的 deck 才拒，裸词只告警。这条改动由端到端测试逼出来，别再改回去。

## 器件族前缀表

R6/R7 判定「像 PDK master 名」用的前缀，写在 `scripts/guard.py` 的 `DEVICE_PREFIXES`：

```
nmos pmos nch pch nfet pfet npn pnp bjt
rpoly rpo polyres poly mim mom moscap var
res cap ind dio diode scr esd ldmos
hvt lvt rvt svt uhvt ulvt sgt dgt hpt hsl
```

判定还要求：token 含至少一个数字、长度 4–40、不在 `STOPWORDS` 里、不在 `_local/own-cells.txt` 里。

`STOPWORDS` 收的是 SPICE/Spectre 关键字、参数名（`w` `l` `nf` `multi` `vth0` …）、单位、常见节点名（`vdd` `vss` `gnd` `n1` …）、corner 名、以及 EDA 工具名。**工具名在 STOPWORDS 里，所以 `calibre` `spectre` `virtuoso` 不会被当成单元名替换掉。**

换新工艺时前缀表要补。改法是编辑 `DEVICE_PREFIXES`，然后跑 `python scripts/outbox.py selftest` 确认没打坏既有判定。

## 手工复查

不必走完整 `commit` 也能扫一份文件：

```
python scripts/guard.py <file.md> --own-cells _local/own-cells.txt --cell-map _local/cell-map.yml
python scripts/guard.py <file.md> --show-substituted     # 顺便打印脱敏后的全文
python scripts/sanitize_bridge.py --selftest             # 第一道机的自检
python scripts/outbox.py selftest                        # 两道机 + 解析 + 校验的 24 项
```

携出前一定要跑：

```
python scripts/outbox.py audit
```

它对每条已定稿记录重扫一遍两道机、复查必填字段、核对 `MANIFEST.md` 与 `index.jsonl` 是否与实体一致。有任何一条不过就退出码 1，`bundle` 也会因此拒绝打包（除非 `--force`）。
