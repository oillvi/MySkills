#!/usr/bin/env python3
"""outbox.py -- the only command the offline model needs.

Design constraints this file obeys (see docs/superpowers/specs/
2026-09-28-outbox-recorder-design.md):

* The DSH `write` tool has NO append mode. A weak model doing read-modify-write
  on a growing log will eventually truncate history. So: one file per record,
  written once, never edited by the model. All mutation of existing files is
  done by THIS script.
* The model's whole job is three steps: `new` -> `edit` the placeholders ->
  `commit`. It never computes an ID, never writes MANIFEST.md or index.jsonl,
  never touches a committed record.
* The red line (no Cadence library data leaves the airgap) is enforced here, not
  in prose: two gates run on every commit, and a rejection prints file:line:rule
  so the model can fix and retry.
* Standard library only. PyYAML is optional; every map/parse path degrades to a
  line parser. This must run on a minimal offline Python.

Commands:
    init                       create the directory skeleton and _local/config.yml
    new --type T               generate a prefilled draft, print its path
    commit <draft>             two gates -> assign id -> file -> rebuild manifest
    list [--status S] [--type T]
    audit                      pre-carry-out health check
    sync-inbox                 merge answer receipts back into records
    bundle [--out PATH]        git commit + git bundle create
    answer <ID> --status S     write an inbox receipt (runs on the outside box)
    selftest                   built-in cases; run this right after installing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import guard as guard_mod
import sanitize_bridge

# --------------------------------------------------------------------------
# vocabulary
# --------------------------------------------------------------------------

TYPES = {
    "problem": ("prob", "撞到的具体问题：工具报错、流程卡死、结果不可信"),
    "wish": ("wish", "想要但当前没有的能力或工具"),
    "bottleneck": ("bneck", "效率或精度瓶颈：能绕但代价大"),
    "need-outside": ("need", "需要从外网获取的资料、手册页、脚本、器件参数"),
    "drift": ("drift", "察觉自己跑飞：重复同一动作、前后矛盾、丢了目标"),
    "skill-proposal": ("prop", "提议的改进方向，供人裁决是否建新技能"),
}
TYPE_DIRS = {t: t for t in TYPES}
STATUS_VALUES = ("pending-review", "approved", "rejected", "answered", "wontfix")
SEVERITY_VALUES = ("blocking", "slowing", "annoyance")

RECORDS = SKILL_ROOT / "records"
DRAFTS = SKILL_ROOT / "drafts"
INBOX = SKILL_ROOT / "inbox"
LOCAL = SKILL_ROOT / "_local"
MANIFEST = SKILL_ROOT / "MANIFEST.md"
INDEX = SKILL_ROOT / "index.jsonl"
CONFIG = LOCAL / "config.yml"
OWN_CELLS = LOCAL / "own-cells.txt"
CELL_MAP = LOCAL / "cell-map.yml"

TITLE_MAX = 60
BODY_MAX_LINES = 200
EVIDENCE_MAX_LINES = 30
DEDUP_THRESHOLD = 0.62

# sections that must carry real content, per type
REQUIRED_SECTIONS = {
    "problem": ["现象", "已试过", "期望的答案长什么样"],
    "wish": ["想要的能力", "为什么现在做不到", "期望的答案长什么样"],
    "bottleneck": ["现象", "当前代价", "期望的答案长什么样"],
    "need-outside": ["要找什么", "用途", "期望的形式"],
    "drift": ["跑飞的表现", "触发点", "期望的约束"],
    "skill-proposal": ["派生自", "观察到的重复动作", "为什么现在做不到",
                       "期望能力一句话", "建议落点"],
}


def now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def today() -> str:
    return time.strftime("%Y-%m-%d")


def die(msg: str, code: int = 1) -> None:
    print(f"[reject] {msg}")
    raise SystemExit(code)


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

def parse_flat(text: str) -> dict[str, str]:
    """Dependency-free flat mapping parser: `key: value` or `key=value`."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        s = line.strip()
        if not s or s.startswith("-"):
            continue
        sep = ":" if ":" in s else ("=" if "=" in s else None)
        if sep is None:
            continue
        k, v = s.split(sep, 1)
        k, v = k.strip(), v.strip().strip("'\"")
        if k:
            out[k] = v
    return out


def load_config() -> dict[str, str]:
    if not CONFIG.exists():
        return {}
    return parse_flat(CONFIG.read_text(encoding="utf-8", errors="replace"))


def cfg(key: str, default: str = "unknown") -> str:
    return load_config().get(key) or os.environ.get(key.upper()) or default


# --------------------------------------------------------------------------
# minimal frontmatter reader / writer (our own controlled shape only)
# --------------------------------------------------------------------------

FRONT_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


def split_doc(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Nested one level (the env: block)."""
    m = FRONT_RE.match(text)
    if not m:
        return {}, text
    fm: dict = {}
    current_key = None
    for raw in m.group(1).splitlines():
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if indent > 0 and current_key and isinstance(fm.get(current_key), dict):
            fm[current_key][k] = _coerce(v)
            continue
        if v == "":
            fm[k] = {}
            current_key = k
            continue
        fm[k] = _coerce(v)
        current_key = None
    return fm, text[m.end():]


def _coerce(v: str):
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip("'\"") for x in inner.split(",")]
    if v.startswith("'") and v.endswith("'"):
        return v[1:-1]
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if v in ("true", "false"):
        return v == "true"
    return v


def dump_front(fm: dict) -> str:
    """Deterministic serializer for the shape split_doc understands."""
    order = ["id", "type", "status", "created", "project", "block", "severity",
             "effort_seen", "class", "related_wiki", "derived_from",
             "recurrences", "env"]
    lines = ["---"]
    keys = [k for k in order if k in fm] + [k for k in fm if k not in order]
    for k in keys:
        v = fm[k]
        if isinstance(v, dict):
            lines.append(f"{k}:")
            for kk, vv in v.items():
                lines.append(f"  {kk}: {vv}")
        elif isinstance(v, list):
            lines.append(f"{k}: [{', '.join(str(x) for x in v)}]")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# templates
# --------------------------------------------------------------------------

TEMPLATES = {
    "problem": """# {{一句话标题，不超过 60 字}}

## 现象
{{发生了什么。原样贴错误信息，不要改写}}

## 已试过
{{每次尝试写一行。没有就写 无}}

## 期望的答案长什么样
{{外网侧要交付什么：一段说明 / 一个脚本 / 一份手册页 / 一个器件参数}}

## 证据
{{可选。只能贴本项目自己的网表，最多 30 行，写进下面围栏里。没有就把整节删掉}}

```
{{网表片段}}
```

## 改进方向
{{可选。没有就写 无}}
""",
    "wish": """# {{一句话标题，不超过 60 字}}

## 想要的能力
{{一句话说清希望具备什么}}

## 为什么现在做不到
{{缺工具 / 缺权限 / 缺知识 / 缺模型能力，指到具体那一环}}

## 期望的答案长什么样
{{外网侧要交付什么。写具体}}

## 优先级理由
{{不做会怎样。可选，没有就写 无}}
""",
    "bottleneck": """# {{一句话标题，不超过 60 字}}

## 现象
{{哪一步慢或不准}}

## 当前代价
{{给出数字：耗时、迭代次数、误差}}

## 期望的答案长什么样
{{外网侧要交付什么。写具体}}

## 证据
{{可选。没有就把整节删掉}}
""",
    "need-outside": """# {{一句话标题，不超过 60 字}}

## 要找什么
{{具体到能直接去搜的程度：文档标题、手册章节、API 名、器件型号}}

## 用途
{{拿到之后用来解决哪条记录或哪个设计步骤}}

## 已知的线索
{{可选。已经知道的出处、版本、关键词。没有就写 无}}

## 期望的形式
{{原文摘录 / PDF 页码 / 可运行脚本 / 一段结论。选一个并说明}}
""",
    "drift": """# {{一句话标题，不超过 60 字}}

## 跑飞的表现
{{重复同一动作 / 前后自相矛盾 / 丢了原目标 / 越权改了不该改的文件}}

## 触发点
{{在哪个任务、哪一步、收到什么输入之后开始跑飞}}

## 已经重复了几次
{{给数字}}

## 期望的约束
{{希望有什么规矩、检查点或脚本来拦住它}}
""",
    "skill-proposal": """# {{一句话标题，不超过 60 字}}

## 派生自
{{写一条已存在的 drift- 或 prob- 记录 ID，例如 prob-0003}}

## 观察到的重复动作
{{你和别的会话反复在做的那件事，写成可复述的步骤}}

## 为什么现在做不到
{{缺什么}}

## 期望能力一句话
{{一句话说清这个技能该干什么}}

## 建议落点
{{四选一：新技能 / 扩哪个现有技能 / 加 checklist 条目 / 改 prompt。写清名字}}

## 预期收益
{{省多少步、少犯什么错。可选，没有就写 无}}
""",
}

FRONT_TEMPLATE = """id: null
type: {type}
status: draft
created: {created}
project: {project}
block: {block}
severity: {severity}
effort_seen: {effort}
class: {klass}
related_wiki: []
derived_from: []
recurrences: 0
env:
  harness: {harness}
  desktop: {desktop}
  arcadia1_sha: {sha}
  model: {model}
"""


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------

CONFIG_TEMPLATE = """# outbox-recorder local config -- never leaves the airgap, never committed.
# Every value is optional; missing values degrade to "unknown".

# Project name stamped into every record's frontmatter.
project: {project}

# Absolute path of the analog-agents checkout, so the first redaction gate can
# reuse arcadia-1's own token map. Leave commented out to auto-detect siblings.
# ANALOG_AGENTS_ROOT: H:/analog-agents

# Environment stamp. Fill these in once; they make records reproducible.
harness: unknown
desktop: unknown
arcadia1_sha: unknown
model: qwen3.8-max-27B

# Which python to use. arcadia-1 forbids the global interpreter; point this at
# the project venv if you want the same discipline.
python: python
"""


def cmd_init(args: argparse.Namespace) -> int:
    created = []
    for d in [RECORDS, DRAFTS, INBOX, INBOX / "_done", LOCAL]:
        d.mkdir(parents=True, exist_ok=True)
        created.append(d)
    for t in TYPES:
        (RECORDS / TYPE_DIRS[t]).mkdir(parents=True, exist_ok=True)
    if not CONFIG.exists():
        CONFIG.write_text(
            CONFIG_TEMPLATE.format(project=args.project or "unknown"), encoding="utf-8"
        )
        created.append(CONFIG)
    if not OWN_CELLS.exists():
        OWN_CELLS.write_text(
            "# Cells THIS project owns. Anything not listed here gets replaced by\n"
            "# a <cell_NNN> placeholder inside code evidence. One name per line.\n"
            "# Lines starting with # are ignored.\n",
            encoding="utf-8",
        )
        created.append(OWN_CELLS)
    if not CELL_MAP.exists():
        CELL_MAP.write_text(
            "# real master name -> stable placeholder. Script-appended. Never carry out.\n",
            encoding="utf-8",
        )
        created.append(CELL_MAP)
    gi = SKILL_ROOT / ".gitignore"
    if not gi.exists():
        gi.write_text(
            "# never leaves the airgap\n_local/\n# transient\ndrafts/\ninbox/_done/\n"
            "__pycache__/\n*.pyc\n",
            encoding="utf-8",
        )
        created.append(gi)
    print(f"[ok] skeleton ready under {SKILL_ROOT}")
    for c in created:
        print(f"     {c.relative_to(SKILL_ROOT)}")
    rebuild_indexes()
    print(f"[ok] {MANIFEST.name} and {INDEX.name} written")
    return 0


# --------------------------------------------------------------------------
# new
# --------------------------------------------------------------------------

def cmd_new(args: argparse.Namespace) -> int:
    if args.type not in TYPES:
        die(f"unknown type {args.type!r}; choose from {', '.join(TYPES)}")
    DRAFTS.mkdir(parents=True, exist_ok=True)
    project = args.project or cfg("project", "{{项目名}}")
    fm = FRONT_TEMPLATE.format(
        type=args.type,
        created=today(),
        project=project,
        block=args.block or "",
        severity="{{blocking | slowing | annoyance}}",
        effort=cfg("effort_seen", "standard"),
        klass="",
        harness=cfg("harness"),
        desktop=cfg("desktop"),
        sha=cfg("arcadia1_sha"),
        model=cfg("model"),
    )
    path = DRAFTS / f"{now_stamp()}__draft__{args.type}.md"
    # never clobber a draft made in the same second
    n = 1
    while path.exists():
        path = DRAFTS / f"{now_stamp()}__draft__{args.type}_{n}.md"
        n += 1
    path.write_text("---\n" + fm + "---\n\n" + TEMPLATES[args.type], encoding="utf-8")
    print(f"[ok] draft created: {path}")
    print("[next] fill every {{...}} placeholder with the edit tool, then run:")
    print(f"       python {Path('scripts')/'outbox.py'} commit \"{path}\"")
    return 0


# --------------------------------------------------------------------------
# commit
# --------------------------------------------------------------------------

def load_own_cells() -> set[str]:
    return guard_mod.load_own_cells(OWN_CELLS)


def load_cell_map() -> dict[str, str]:
    return guard_mod.load_cell_map(CELL_MAP)


def save_cell_map(cmap: dict[str, str]) -> None:
    if not cmap:
        return
    CELL_MAP.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# real master name -> stable placeholder. Script-appended. Never carry out."]
    for k in sorted(cmap):
        lines.append(f"{k}: {cmap[k]}")
    CELL_MAP.write_text("\n".join(lines) + "\n", encoding="utf-8")


def next_id(prefix: str) -> str:
    best = 0
    if RECORDS.exists():
        for p in RECORDS.rglob("*.md"):
            m = re.search(rf"__{re.escape(prefix)}-(\d+)__", p.name)
            if m:
                best = max(best, int(m.group(1)))
    return f"{prefix}-{best + 1:04d}"


def slugify(title: str) -> str:
    toks = re.findall(r"[a-z0-9]+", title.lower())
    slug = "-".join(toks)[:40].strip("-")
    return slug or "note"


def extract_title(body: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return ""


def section_text(body: str, heading: str) -> str:
    """Return the content under `## heading`, up to the next `##`."""
    lines = body.splitlines()
    out, inside = [], False
    for line in lines:
        s = line.strip()
        if s.startswith("## "):
            if inside:
                break
            inside = s[3:].strip() == heading
            continue
        if inside:
            out.append(line)
    return "\n".join(out).strip()


def tokens_for_sim(text: str) -> set[str]:
    """CJK bigrams + ascii words. Cheap and adequate for near-duplicate titles."""
    ascii_words = set(re.findall(r"[a-z0-9]+", text.lower()))
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    bigrams = {"".join(p) for p in zip(cjk, cjk[1:])}
    return ascii_words | bigrams


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens_for_sim(a), tokens_for_sim(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def find_duplicate_proposal(title: str, body: str) -> Path | None:
    d = RECORDS / TYPE_DIRS["skill-proposal"]
    if not d.exists():
        return None
    best, best_score = None, 0.0
    for p in sorted(d.glob("*.md")):
        fm, b = split_doc(p.read_text(encoding="utf-8", errors="replace"))
        score = jaccard(title, str(fm.get("title") or extract_title(b)))
        score = max(score, jaccard(body, b) * 0.9)
        if score > best_score:
            best, best_score = p, score
    if best is not None and best_score >= DEDUP_THRESHOLD:
        print(f"[warn] near-duplicate of {best.name} (similarity {best_score:.2f})")
        return best
    if best is not None and best_score >= 0.35:
        print(f"[warn] similar but distinct from {best.name} "
              f"(similarity {best_score:.2f} < {DEDUP_THRESHOLD}); keeping both")
    return None


def bump_recurrence(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    fm, body = split_doc(text)
    fm["recurrences"] = int(fm.get("recurrences") or 0) + 1
    stamp = time.strftime("%Y-%m-%d %H:%M")
    marker = "## 再次出现"
    if marker not in body:
        body = body.rstrip() + f"\n\n{marker}\n- {stamp}\n"
    else:
        body = body.rstrip() + f"\n- {stamp}\n"
    path.write_text(dump_front(fm) + "\n" + body.lstrip("\n"), encoding="utf-8")


def validate(fm: dict, body: str, rtype: str) -> list[str]:
    errs: list[str] = []
    title = extract_title(body)
    if not title:
        errs.append("missing a `# title` line as the first heading of the body")
    elif len(title) > TITLE_MAX:
        errs.append(f"title is {len(title)} chars, limit is {TITLE_MAX}")
    if fm.get("project") in (None, "", "unknown", "{{项目名}}"):
        errs.append("frontmatter project is empty; set project: in _local/config.yml "
                    "or pass --project to `new`")
    if fm.get("severity") not in SEVERITY_VALUES:
        errs.append(f"severity must be one of {', '.join(SEVERITY_VALUES)}; "
                    f"got {fm.get('severity')!r}")
    for sec in REQUIRED_SECTIONS.get(rtype, []):
        content = section_text(body, sec)
        if not content:
            errs.append(f"section `## {sec}` is required for type {rtype} and is empty")
        elif content.strip() in ("无", "None", "N/A") and sec in (
            "现象", "已试过", "期望的答案长什么样", "想要的能力",
            "为什么现在做不到", "要找什么", "期望的形式", "跑飞的表现",
            "触发点", "期望的约束", "派生自", "观察到的重复动作",
            "期望能力一句话", "建议落点",
        ):
            errs.append(f"section `## {sec}` cannot be `无`; it is required content")
    if rtype == "skill-proposal":
        df = fm.get("derived_from") or []
        if isinstance(df, str):
            df = [x.strip() for x in re.split(r"[,\s]+", df) if x.strip()]
        if not df:
            errs.append("skill-proposal requires derived_from: [<drift- or prob- id>]")
        else:
            for ref in df:
                if not resolve_id(ref):
                    errs.append(f"derived_from refers to {ref} which does not exist")
                elif not (ref.startswith("drift-") or ref.startswith("prob-")):
                    errs.append(f"derived_from must point at a drift- or prob- record, "
                                f"got {ref}")
    wiki = fm.get("related_wiki") or []
    if isinstance(wiki, list):
        for ref in wiki:
            if ref and not re.match(r"^(topo|strat|corner|anti|proj|case)-\d+", str(ref)):
                errs.append(f"related_wiki entry {ref!r} does not look like an "
                            "arcadia-1 wiki id (topo-/strat-/corner-/anti-/proj-/case-)")
    return errs


def resolve_id(rid: str) -> Path | None:
    if not RECORDS.exists():
        return None
    for p in RECORDS.rglob("*.md"):
        if f"__{rid}__" in p.name:
            return p
    return None


def cmd_commit(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    if not draft.exists():
        die(f"no such draft: {draft}")
    text = draft.read_text(encoding="utf-8", errors="replace")
    fm, body = split_doc(text)
    rtype = str(fm.get("type") or "")
    if rtype not in TYPES:
        die(f"draft frontmatter has type={rtype!r}; expected one of {', '.join(TYPES)}")

    # ---- gate 1: arcadia-1 token map ------------------------------------
    bridge = sanitize_bridge.get_bridge()
    print(f"[gate1] {bridge.describe()}")
    for w in bridge.warnings:
        print(f"[warn] {w}")
    text, hits = bridge.apply(text)
    for src, dst, n in hits:
        print(f"[gate1] {n}x {src!r} -> {dst!r}")

    # ---- gate 2: structural detection -----------------------------------
    own = load_own_cells()
    cmap = load_cell_map()
    res = guard_mod.scan(text, own, cmap)
    if res["rejects"]:
        print(f"[reject] {len(res['rejects'])} guard rule hit(s) in {draft.name}")
        for f in res["rejects"]:
            print(f.render(str(draft)))
        print("[next] fix each line above with the edit tool, then commit again. "
              "The draft is kept.")
        return 1
    for w in res["warns"]:
        print(f"[warn] {w.rule} line {w.line}: {w.note}")
    text = res["text"]
    if res["subs"]:
        save_cell_map(cmap)
        shown = ", ".join(f"{r}->{p}" for r, p in res["subs"][:12])
        more = "" if len(res["subs"]) <= 12 else f" (+{len(res['subs']) - 12} more)"
        print(f"[gate2] substituted {len(res['subs'])} master name(s): {shown}{more}")

    fm, body = split_doc(text)
    # A weak model fills prose more reliably than frontmatter. If it wrote an ID
    # into the `## 派生自` section but left derived_from empty, take it from there
    # instead of rejecting -- one less way for the three-step protocol to stall.
    if rtype == "skill-proposal" and not (fm.get("derived_from") or []):
        found = re.findall(r"\b(?:drift|prob)-\d{4}\b", section_text(body, "派生自"))
        if found:
            fm["derived_from"] = sorted(set(found))
            text = dump_front(fm) + "\n" + body.lstrip("\n")
            print(f"[ok] derived_from taken from the 派生自 section: {fm['derived_from']}")
    errs = validate(fm, body, rtype)
    if errs:
        print(f"[reject] {len(errs)} content problem(s) in {draft.name}")
        for e in errs:
            print(f"  [reject] {e}")
        print("[next] fix with the edit tool, then commit again. The draft is kept.")
        return 1

    title = extract_title(body)

    # ---- de-duplicate proposals -----------------------------------------
    if rtype == "skill-proposal" and not args.force:
        dup = find_duplicate_proposal(title, body)
        if dup is not None:
            bump_recurrence(dup)
            draft.unlink()
            print(f"[ok] not a new proposal: counted as a recurrence of {dup.name}")
            rebuild_indexes()
            return 0

    # ---- assign id, file it ---------------------------------------------
    prefix = TYPES[rtype][0]
    rid = next_id(prefix)
    fm["id"] = rid
    fm["status"] = "pending-review"
    fm.setdefault("recurrences", 0)
    target_dir = RECORDS / TYPE_DIRS[rtype]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{now_stamp()}__{rid}__{slugify(title)}.md"
    target.write_text(dump_front(fm) + "\n" + body.lstrip("\n"), encoding="utf-8")
    draft.unlink()
    rebuild_indexes()
    print(f"[ok] committed {rid} -> {target.relative_to(SKILL_ROOT)}")
    print(f"[ok] {MANIFEST.name} and {INDEX.name} rebuilt")
    return 0


# --------------------------------------------------------------------------
# indexes
# --------------------------------------------------------------------------

def all_records() -> list[tuple[Path, dict, str, str]]:
    """Every committed record as (path, frontmatter, title, body)."""
    out = []
    if not RECORDS.exists():
        return out
    for p in sorted(RECORDS.rglob("*.md")):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm, body = split_doc(text)
        if not fm.get("id"):
            continue
        out.append((p, fm, extract_title(body), body))
    return out


def rebuild_indexes() -> None:
    rows = all_records()
    lines = [
        "# outbox MANIFEST",
        "",
        f"Generated by `outbox.py`. Do not edit by hand. {len(rows)} record(s).",
        f"Regenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    by_status: dict[str, list] = {}
    for p, fm, title, _body in rows:
        by_status.setdefault(str(fm.get("status")), []).append((p, fm, title))
    order = ["pending-review", "approved", "answered", "rejected", "wontfix", "draft"]
    for st in order + [s for s in by_status if s not in order]:
        group = by_status.get(st)
        if not group:
            continue
        lines.append(f"## {st} ({len(group)})")
        lines.append("")
        lines.append("| id | type | severity | project | recurrences | created | title |")
        lines.append("|---|---|---|---|---|---|---|")
        for p, fm, title in sorted(group, key=lambda r: str(r[1].get("id"))):
            lines.append(
                f"| {fm.get('id')} | {fm.get('type')} | {fm.get('severity', '')} "
                f"| {fm.get('project', '')} | {fm.get('recurrences', 0)} "
                f"| {fm.get('created', '')} | {title[:TITLE_MAX]} |"
            )
        lines.append("")
    if not rows:
        lines.append("_No records yet._")
        lines.append("")
    MANIFEST.write_text("\n".join(lines), encoding="utf-8")

    with INDEX.open("w", encoding="utf-8") as fh:
        for p, fm, title, _body in rows:
            rec = dict(fm)
            rec["title"] = title
            rec["path"] = str(p.relative_to(SKILL_ROOT)).replace(os.sep, "/")
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


# --------------------------------------------------------------------------
# list / audit
# --------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    rows = all_records()
    if args.status:
        rows = [r for r in rows if str(r[1].get("status")) == args.status]
    if args.type:
        rows = [r for r in rows if str(r[1].get("type")) == args.type]
    if not rows:
        print("[ok] no records match")
        return 0
    print(f"[ok] {len(rows)} record(s)")
    for p, fm, title, _body in rows:
        print(f"  {fm.get('id'):<12} {fm.get('status')!s:<15} "
              f"{fm.get('severity')!s:<9} {title[:50]}")
        print(f"               {p.relative_to(SKILL_ROOT)}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    rows = all_records()
    problems: list[str] = []
    bridge = sanitize_bridge.get_bridge()
    own = load_own_cells()
    print(f"[info] {len(rows)} record(s); gate1 {bridge.describe()}")
    for p, fm, _title, body in rows:
        text = p.read_text(encoding="utf-8", errors="replace")
        res = guard_mod.scan(text, own, {})
        if res["rejects"]:
            problems.append(f"{p.name}: {len(res['rejects'])} guard hit(s), "
                            f"first = {res['rejects'][0].rule} line {res['rejects'][0].line}")
        for e in validate(fm, body, str(fm.get("type"))):
            problems.append(f"{p.name}: {e}")
        nlines = len(text.splitlines())
        if nlines > BODY_MAX_LINES * 2:
            problems.append(f"{p.name}: {nlines} lines, over the hard cap "
                            f"{BODY_MAX_LINES * 2}")
    # index consistency
    idx_ids = set()
    if INDEX.exists():
        for line in INDEX.read_text(encoding="utf-8").splitlines():
            if line.strip():
                idx_ids.add(json.loads(line).get("id"))
    rec_ids = {str(fm.get("id")) for _, fm, _, _ in rows}
    if idx_ids != rec_ids:
        problems.append(f"index.jsonl out of sync: missing {sorted(rec_ids - idx_ids)}, "
                        f"orphan {sorted(idx_ids - rec_ids)}")
    if MANIFEST.exists():
        mtext = MANIFEST.read_text(encoding="utf-8")
        for rid in sorted(rec_ids):
            if rid not in mtext:
                problems.append(f"MANIFEST.md does not mention {rid}")
    else:
        problems.append("MANIFEST.md is missing")
    stray = list(DRAFTS.glob("*.md")) if DRAFTS.exists() else []
    warns: list[str] = []
    if stray:
        # A rejected commit deliberately KEEPS its draft so the model can fix and
        # retry, so work-in-progress drafts are normal. They are gitignored and
        # never travel in a bundle; only --strict turns them into a failure.
        msg = (f"{len(stray)} work-in-progress draft(s) in drafts/: "
               + ", ".join(s.name for s in stray[:5]))
        (problems if getattr(args, "strict", False) else warns).append(msg)

    for w in warns:
        print(f"[warn] {w}")
    if problems:
        print(f"[reject] audit found {len(problems)} problem(s)")
        for x in problems:
            print(f"  - {x}")
        return 1
    print("[ok] audit clean: guard passes on every record, indexes consistent"
          + ("" if not warns else f", {len(warns)} warning(s) noted")
          + ". Safe to carry out.")
    return 0


# --------------------------------------------------------------------------
# inbox / answer
# --------------------------------------------------------------------------

def cmd_answer(args: argparse.Namespace) -> int:
    if args.status not in STATUS_VALUES:
        die(f"status must be one of {', '.join(STATUS_VALUES)}")
    if not resolve_id(args.id) and not args.allow_missing:
        print(f"[warn] no record with id {args.id} under {RECORDS}; "
              "writing the receipt anyway (use --allow-missing to silence)")
    INBOX.mkdir(parents=True, exist_ok=True)
    path = INBOX / f"{args.id}.md"
    note = (args.note or "").replace("\n", " ").strip()
    path.write_text(
        "---\n"
        f"id: {args.id}\n"
        f"status: {args.status}\n"
        f"answered: {today()}\n"
        f"note: {json.dumps(note, ensure_ascii=False)}\n"
        "---\n",
        encoding="utf-8",
    )
    print(f"[ok] receipt written: {path}")
    print("[next] carry this file into the airgap, then run: "
          "python scripts/outbox.py sync-inbox")
    return 0


def cmd_sync_inbox(args: argparse.Namespace) -> int:
    if not INBOX.exists():
        print("[ok] no inbox")
        return 0
    files = [p for p in INBOX.glob("*.md")]
    if not files:
        print("[ok] inbox is empty")
        return 0
    done_dir = INBOX / "_done"
    done_dir.mkdir(parents=True, exist_ok=True)
    merged = 0
    for f in files:
        fm, _ = split_doc(f.read_text(encoding="utf-8", errors="replace"))
        rid = str(fm.get("id") or "")
        target = resolve_id(rid)
        if target is None:
            print(f"[warn] receipt {f.name} refers to {rid or '<none>'}, "
                  "which does not exist here; left in inbox")
            continue
        status = str(fm.get("status") or "")
        if status not in STATUS_VALUES:
            print(f"[warn] receipt {f.name} has status {status!r}; left in inbox")
            continue
        text = target.read_text(encoding="utf-8")
        tfm, tbody = split_doc(text)
        tfm["status"] = status
        note = fm.get("note") or ""
        block = "## 外网回执"
        entry = f"- {fm.get('answered', today())} status={status}"
        if note:
            entry += f" note={note}"
        if block in tbody:
            tbody = tbody.rstrip() + f"\n{entry}\n"
        else:
            tbody = tbody.rstrip() + f"\n\n{block}\n{entry}\n"
        target.write_text(dump_front(tfm) + "\n" + tbody.lstrip("\n"), encoding="utf-8")
        shutil.move(str(f), str(done_dir / f.name))
        merged += 1
        print(f"[ok] {rid} -> {status}")
    rebuild_indexes()
    print(f"[ok] merged {merged} receipt(s); indexes rebuilt")
    return 0


# --------------------------------------------------------------------------
# bundle
# --------------------------------------------------------------------------

def _git(*a: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *a], cwd=str(SKILL_ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return 127, "git not found on PATH"


def cmd_bundle(args: argparse.Namespace) -> int:
    code, out = _git("rev-parse", "--is-inside-work-tree")
    if code != 0:
        print("[info] not a git repo yet; initialising")
        code, out = _git("init", "-q")
        if code != 0:
            die(f"git init failed: {out.strip()}")
    audit_code = cmd_audit(args)
    if audit_code != 0 and not args.force:
        print("[reject] audit failed; fix the problems above or re-run with --force")
        return 1
    _git("add", "-A")
    code, out = _git("status", "--porcelain")
    if out.strip():
        code, out = _git("-c", "user.name=outbox-recorder",
                         "-c", "user.email=outbox@localhost",
                         "commit", "-q", "-m",
                         f"outbox: {len(all_records())} record(s) {time.strftime('%Y-%m-%d %H:%M')}")
        if code != 0:
            die(f"git commit failed: {out.strip()}")
        print("[ok] committed pending changes")
    else:
        print("[ok] nothing to commit")
    out_path = Path(args.out) if args.out else SKILL_ROOT.parent / f"outbox-{today()}.bundle"
    code, out = _git("bundle", "create", str(out_path), "--all")
    if code != 0:
        die(f"git bundle failed: {out.strip()}")
    size = out_path.stat().st_size if out_path.exists() else -1
    print(f"[ok] bundle -> {out_path} ({size} bytes, {len(all_records())} record(s))")
    print("[next] carry that one file out. On the outside box: "
          "git clone <bundle> outbox-inbox")
    return 0


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------

CLEAN_RECORD = """---
id: null
type: problem
status: draft
created: 2026-09-28
project: demo-project
block: comparator
severity: blocking
effort_seen: standard
class: lv-nmos
related_wiki: [anti-003]
derived_from: []
recurrences: 0
env:
  harness: unknown
  desktop: unknown
  arcadia1_sha: unknown
  model: qwen3.8-max-27B
---

# Regeneration stops after three corners

## 现象
ADE XL stops after corner 3 and prints `cannot open raw file`.
The remaining four corners never run.

## 已试过
- restarted the simulation, same stop at corner 3
- deleted the results directory, same stop

## 期望的答案长什么样
A short explanation of what makes corner 3 different, plus the exact
setting or command that lets the remaining corners run.

## 证据
```
M1 (out in vss vss) <cell_001> w=2u l=0.18u m=2 nf=2
R1 (out fb) <cell_002> r=10k
```

## 改进方向
无
"""

DIRTY_RECORD = """---
id: null
type: problem
status: draft
created: 2026-09-28
project: demo-project
block: ldo
severity: blocking
effort_seen: standard
class: lv-nmos
related_wiki: []
derived_from: []
recurrences: 0
env:
  harness: unknown
  desktop: unknown
  arcadia1_sha: unknown
  model: qwen3.8-max-27B
---

# Model card leaked on purpose

## 现象
include "/eda/pdk/tsmc18/models/spectre/tt.scs"
model nmos1v nmos level=49 vth0=0.55
Library name: analogLib
techfile: tsmc18.tf
Run from H:\\analog-agents\\WORK_ldo

## 已试过
无

## 期望的答案长什么样
无
"""


def cmd_selftest(args: argparse.Namespace) -> int:
    failures: list[str] = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        print(f"  [{'ok' if cond else 'FAIL'}] {label}" + (f" -- {detail}" if detail and not cond else ""))
        if not cond:
            failures.append(label)

    print("[selftest] gate 2: guard on a clean record")
    res = guard_mod.scan(CLEAN_RECORD, {"myowncell"}, {})
    check("clean record has no rejects", not res["rejects"],
          "; ".join(f.render() for f in res["rejects"][:4]))

    print("[selftest] gate 2: guard on a dirty record")
    res = guard_mod.scan(DIRTY_RECORD, set(), {})
    rules = {f.rule for f in res["rejects"]}
    for want in ("R2", "R1", "R4", "R5", "R3"):
        check(f"dirty record trips {want}", want in rules, f"got {sorted(rules)}")

    print("[selftest] gate 2: R3 rejects data but not vocabulary")
    vocab = "The Calibre DRC run reported 12 violations on metal1 spacing.\n"
    res = guard_mod.scan(vocab, set(), {})
    check("naming a tool and a check is allowed", not res["rejects"],
          "; ".join(f.render() for f in res["rejects"][:3]))
    check("...but it raises a W2 warn for the human",
          any(w.rule == "W2" for w in res["warns"]))
    res = guard_mod.scan("exported analogLib.oa and rules.svrf\n", set(), {})
    check("a deck file name is still rejected",
          any(f.rule == "R3" for f in res["rejects"]))

    print("[selftest] regression: every shipped template is guard-clean")
    for tname, tpl in TEMPLATES.items():
        res = guard_mod.scan(tpl, set(), {})
        bad = [f for f in res["rejects"] if f.rule != "R0"]
        check(f"template {tname}: only R0 (placeholder) hits", not bad,
              "; ".join(f.render() for f in bad[:3]))

    print("[selftest] gate 2: R0 catches an unfilled placeholder")
    res = guard_mod.scan("# t\n\n## 现象\n{{发生了什么}}\n", set(), {})
    check("R0 fires", any(f.rule == "R0" for f in res["rejects"]))

    print("[selftest] gate 2: R6 substitutes a master name inside a code fence")
    cmap: dict[str, str] = {}
    src = "```\nM1 (a b c d) nmos1v w=1u l=0.18u\n```\n"
    out, subs = guard_mod.substitute_masters(src, {"myowncell"}, cmap)
    check("master replaced", "nmos1v" not in out and "<cell_001>" in out, out.strip())
    check("substitution reported", subs == [("nmos1v", "<cell_001>")], str(subs))
    check("map recorded", cmap.get("nmos1v") == "<cell_001>", str(cmap))
    check("own cell untouched",
          guard_mod.substitute_masters("```\nX1 (a b) myowncell\n```\n", {"myowncell"}, {})[1] == [])

    print("[selftest] gate 2: R7 rejects a PDK-looking name in prose")
    res = guard_mod.scan("The nmos1v device will not turn on.\n", set(), {})
    check("R7 fires in prose", any(f.rule == "R7" for f in res["rejects"]))
    res = guard_mod.scan("The nmos1v device will not turn on.\n", {"nmos1v"}, set())
    check("R7 respects the own-cells whitelist",
          not any(f.rule == "R7" for f in res["rejects"]))

    print("[selftest] gate 1: sanitize bridge degrades without crashing")
    b = sanitize_bridge.get_bridge()
    txt, hits = b.apply("path /home/wave/x and /eda/pdk/y")
    check("builtin map applied", "<userhome>" in txt and "<edapath>" in txt, txt)
    check("hits reported for the log", len(hits) == 2, str(hits))

    print("[selftest] frontmatter round-trip")
    fm, body = split_doc(CLEAN_RECORD)
    check("id parsed", fm.get("id") == "null", str(fm.get("id")))
    check("nested env parsed", isinstance(fm.get("env"), dict) and "model" in fm["env"],
          str(fm.get("env")))
    check("list parsed", fm.get("related_wiki") == ["anti-003"], str(fm.get("related_wiki")))
    check("body starts at the title", body.lstrip().startswith("# Regeneration"))
    rt = split_doc(dump_front(fm) + "\n" + body)[0]
    check("round-trip stable", rt.get("type") == fm.get("type")
          and rt.get("env") == fm.get("env"), str(rt))

    print("[selftest] validation")
    errs = validate(fm, CLEAN_RECORD.split("---", 2)[2], "problem")
    check("clean record validates", not errs, "; ".join(errs))
    bad_fm = dict(fm)
    bad_fm["severity"] = "catastrophic"
    errs = validate(bad_fm, CLEAN_RECORD.split("---", 2)[2], "problem")
    check("bad severity rejected", any("severity" in e for e in errs))

    print("[selftest] section extraction")
    check("现象 extracted", section_text(CLEAN_RECORD.split("---", 2)[2], "现象")
          .startswith("ADE XL"))
    check("missing section returns empty", section_text("## a\nx\n", "b") == "")

    print("[selftest] id / slug helpers")
    check("slugify ascii", slugify("Regeneration stops after 3 corners")
          == "regeneration-stops-after-3-corners")
    check("slugify cjk falls back", slugify("比较器不收敛") == "note")
    check("next_id shape", re.fullmatch(r"prob-\d{4}", next_id("prob")) is not None)

    print("[selftest] similarity")
    check("identical titles score 1.0", jaccard("同一件事", "同一件事") == 1.0)
    check("unrelated titles score low", jaccard("比较器不收敛", "bundle 无法生成") < 0.3)

    print()
    if failures:
        print(f"[FAIL] selftest failures={len(failures)}: {', '.join(failures)}")
        return 1
    print("[ok] selftest all green")
    return 0


# --------------------------------------------------------------------------
# argparse
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="outbox.py",
        description="Airgap outbox recorder. The model only needs new/commit.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create the directory skeleton")
    p.add_argument("--project", default=None)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("new", help="generate a prefilled draft")
    p.add_argument("--type", required=True, choices=sorted(TYPES))
    p.add_argument("--project", default=None)
    p.add_argument("--block", default=None)
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("commit", help="run both gates and file the record")
    p.add_argument("draft")
    p.add_argument("--force", action="store_true", help="skip proposal de-duplication")
    p.set_defaults(func=cmd_commit)

    p = sub.add_parser("list", help="list records")
    p.add_argument("--status", default=None)
    p.add_argument("--type", default=None)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("audit", help="pre-carry-out health check")
    p.add_argument("--strict", action="store_true",
                   help="treat work-in-progress drafts as a failure")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("sync-inbox", help="merge answer receipts into records")
    p.set_defaults(func=cmd_sync_inbox)

    p = sub.add_parser("bundle", help="git commit + git bundle create")
    p.add_argument("--out", default=None)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_bundle)

    p = sub.add_parser("answer", help="write an inbox receipt (outside box)")
    p.add_argument("id")
    p.add_argument("--status", required=True)
    p.add_argument("--note", default=None)
    p.add_argument("--allow-missing", action="store_true")
    p.set_defaults(func=cmd_answer)

    p = sub.add_parser("selftest", help="run the built-in cases")
    p.set_defaults(func=cmd_selftest)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
