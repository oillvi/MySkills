#!/usr/bin/env python3
"""End-to-end harness for outbox-recorder. Runs in a throwaway copy of the skill
tree so no test record ever lands in the deliverable.

Covers the full lifecycle a human and the offline model will actually exercise:
  init -> new -> (fill placeholders) -> commit   [clean path]
  commit rejection on library data               [gate 2]
  commit rejection on unfilled placeholders      [gate 2 R0]
  skill-proposal without derived_from            [validation]
  skill-proposal with derived_from               [ok]
  duplicate proposal                             [recurrence, not a new file]
  list / audit                                   [indexes]
  answer + sync-inbox                            [receipt loop]
  bundle                                         [carry-out artifact]

Usage:  python e2e_outbox.py [--keep]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(r"E:\Work\Qoder Projects\MySkills\DSH improve\outbox-recorder")
PY = sys.executable

results: list[tuple[str, bool, str]] = []


def record(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"\n        {detail}" if detail and not ok else ""))


def run(cwd: Path, *argv: str, expect: int = 0) -> tuple[int, str]:
    p = subprocess.run([PY, *argv], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def git(cwd: Path, *argv: str) -> tuple[int, str]:
    """Run git itself. `run` prepends the python interpreter, so it cannot be
    used for this -- an earlier revision silently "passed" two git checks
    because the command had errored and produced empty output."""
    p = subprocess.run(["git", *argv], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def outbox(cwd: Path, *argv: str) -> tuple[int, str]:
    return run(cwd, str(cwd / "scripts" / "outbox.py"), *argv)


def fill(path: Path, mapping: dict[str, str]) -> None:
    """Simulate the model's `edit` calls: replace each {{...}} placeholder."""
    text = path.read_text(encoding="utf-8")
    for marker, value in mapping.items():
        text = text.replace(marker, value)
    path.write_text(text, encoding="utf-8")


def newest_draft(cwd: Path) -> Path:
    drafts = sorted((cwd / "drafts").glob("*.md"), key=lambda p: p.stat().st_mtime)
    return drafts[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="do not delete the temp tree")
    args = ap.parse_args()

    if not SRC.exists():
        print(f"[FAIL] source tree missing: {SRC}")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="outbox-e2e-"))
    cwd = tmp / "outbox-recorder"
    shutil.copytree(SRC, cwd, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"[info] test tree: {cwd}\n")

    # ---- init ----------------------------------------------------------
    print("[step] init")
    code, out = outbox(cwd, "init", "--project", "e2e-demo")
    record("init exits 0", code == 0, out[-400:])
    for d in ("records", "drafts", "inbox", "_local"):
        record(f"{d}/ exists", (cwd / d).is_dir())
    record("_local/config.yml written", (cwd / "_local" / "config.yml").is_file())
    record("MANIFEST.md written", (cwd / "MANIFEST.md").is_file())
    record("index.jsonl written", (cwd / "index.jsonl").is_file())

    # ---- clean commit --------------------------------------------------
    print("\n[step] new -> fill -> commit (clean problem record)")
    code, out = outbox(cwd, "new", "--type", "problem", "--block", "comparator")
    record("new exits 0", code == 0, out[-300:])
    record("new printed a path", "draft created:" in out, out[-300:])
    draft = newest_draft(cwd)
    record("draft file exists", draft.is_file(), str(draft))
    body_text = draft.read_text(encoding="utf-8")
    record("draft carries placeholders", "{{" in body_text)
    record("draft frontmatter has type", re.search(r"^type: problem$", body_text, re.M) is not None)

    fill(draft, {
        "{{一句话标题，不超过 60 字}}": "Corner sweep stops after the third corner",
        "{{发生了什么。原样贴错误信息，不要改写}}":
            "ADE XL stops after corner 3 and prints `cannot open raw file`.",
        "{{每次尝试写一行。没有就写 无}}":
            "- restarted the sweep, same stop at corner 3\n- cleared results, same stop",
        "{{外网侧要交付什么：一段说明 / 一个脚本 / 一份手册页 / 一个器件参数}}":
            "The setting that lets the remaining corners run, plus why corner 3 differs.",
        "{{可选。只能贴本项目自己的网表，最多 30 行，写进下面围栏里。没有就把整节删掉}}":
            "本项目比较器网表片段",
        "{{网表片段}}":
            "M1 (out in vss vss) nmos1v w=2u l=0.18u m=2 nf=2\n"
            "R1 (out fb) rpoly_1k r=10k",
        "{{可选。没有就写 无}}": "无",
        "{{blocking | slowing | annoyance}}": "blocking",
    })
    code, out = outbox(cwd, "commit", str(draft))
    record("clean commit exits 0", code == 0, out[-900:])
    record("commit assigned an id", "prob-0001" in out, out[-500:])
    record("commit reported substitution", "substituted" in out and "<cell_" in out, out[-600:])
    record("draft consumed", not draft.exists())
    filed = list((cwd / "records" / "problem").glob("*prob-0001*.md"))
    record("record filed under records/problem/", len(filed) == 1, str(filed))
    if filed:
        txt = filed[0].read_text(encoding="utf-8")
        record("no real master name survived", "nmos1v" not in txt and "rpoly_1k" not in txt,
               [l for l in txt.splitlines() if "cell_" in l or "nmos" in l][:3].__str__())
        record("status is pending-review", "status: pending-review" in txt)
        record("id in frontmatter", "id: prob-0001" in txt)

    # ---- gate 2 rejection ---------------------------------------------
    print("\n[step] commit rejection on Cadence library data")
    outbox(cwd, "new", "--type", "problem")
    draft = newest_draft(cwd)
    fill(draft, {
        "{{一句话标题，不超过 60 字}}": "Leaky record on purpose",
        "{{发生了什么。原样贴错误信息，不要改写}}":
            'include "/eda/pdk/tsmc18/models/spectre/tt.scs"\n'
            "model nmos1v nmos level=49 vth0=0.55\n"
            "Library name: analogLib\n"
            "techfile: tsmc18.tf\n"
            "Run from H:\\\\analog-agents\\\\WORK_ldo",
        "{{每次尝试写一行。没有就写 无}}": "- none",
        "{{外网侧要交付什么：一段说明 / 一个脚本 / 一份手册页 / 一个器件参数}}":
            "Nothing, this is a negative test.",
        "{{可选。只能贴本项目自己的网表，最多 30 行，写进下面围栏里。没有就把整节删掉}}":
            "deliberately left in place so R0 fires too",
        "{{网表片段}}": "M9 (a b c d) pmos_hvt w=1u l=0.18u",
        "{{可选。没有就写 无}}": "无",
        "{{blocking | slowing | annoyance}}": "blocking",
    })
    code, out = outbox(cwd, "commit", str(draft))
    record("dirty commit exits non-zero", code != 0, f"code={code}")
    for rule in ("R1", "R2", "R3", "R4", "R5", "R7"):
        record(f"rejection cites {rule}", rule in out, out[-1200:])
    record("rejection prints a line number", re.search(r":\d+\s+R\d:", out) is not None,
           out[-600:])
    record("draft kept for retry", draft.exists())
    record("no record filed", not list((cwd / "records" / "problem").glob("*prob-0002*")))

    # ---- R0 placeholder rejection --------------------------------------
    print("\n[step] commit rejection on unfilled placeholders")
    outbox(cwd, "new", "--type", "wish")
    draft = newest_draft(cwd)
    fill(draft, {"{{blocking | slowing | annoyance}}": "slowing"})  # leave the rest
    code, out = outbox(cwd, "commit", str(draft))
    record("unfilled draft exits non-zero", code != 0, f"code={code}")
    record("R0 cited", "R0" in out, out[-500:])
    draft.unlink()

    # ---- skill-proposal validation -------------------------------------
    PROP_FILL = {
        "{{一句话标题，不超过 60 字}}": "Add a corner sweep recovery skill",
        "{{你和别的会话反复在做的那件事，写成可复述的步骤}}":
            "Every sweep failure needs the same four manual recovery steps.",
        "{{缺什么}}": "No scripted recovery path exists.",
        "{{一句话说清这个技能该干什么}}":
            "Detect a stalled corner sweep and restart it from the last good corner.",
        "{{四选一：新技能 / 扩哪个现有技能 / 加 checklist 条目 / 改 prompt。写清名字}}":
            "新技能 corner-sweep-recovery",
        "{{省多少步、少犯什么错。可选，没有就写 无}}": "无",
        "{{blocking | slowing | annoyance}}": "slowing",
    }

    print("\n[step] skill-proposal without a real derived_from is rejected")
    outbox(cwd, "new", "--type", "skill-proposal")
    draft = newest_draft(cwd)
    fill(draft, dict(PROP_FILL, **{
        "{{写一条已存在的 drift- 或 prob- 记录 ID，例如 prob-0003}}": "无",
    }))
    text = draft.read_text(encoding="utf-8")
    record("draft frontmatter has empty derived_from", "derived_from: []" in text)
    code, out = outbox(cwd, "commit", str(draft))
    record("proposal without derived_from rejected", code != 0, f"code={code}\n{out[-600:]}")
    record("error names derived_from", "derived_from" in out, out[-400:])

    print("\n[step] filling the 派生自 section alone is enough (auto-derive)")
    fill(draft, {"## 派生自\n无": "## 派生自\nprob-0001"})
    code, out = outbox(cwd, "commit", str(draft))
    record("proposal commits", code == 0, out[-800:])
    record("commit reports the auto-derive", "derived_from taken from" in out, out[-500:])
    record("proposal got prop- id", "prop-0001" in out, out[-400:])
    propfile = next(iter((cwd / "records" / "skill-proposal").glob("*.md")), None)
    if propfile:
        record("derived_from landed in frontmatter",
               "derived_from: [prob-0001]" in propfile.read_text(encoding="utf-8"))

    print("\n[step] duplicate proposal becomes a recurrence")
    outbox(cwd, "new", "--type", "skill-proposal")
    draft = newest_draft(cwd)
    fill(draft, dict(PROP_FILL, **{
        "{{写一条已存在的 drift- 或 prob- 记录 ID，例如 prob-0003}}": "prob-0001",
    }))
    code, out = outbox(cwd, "commit", str(draft))
    record("duplicate commit exits 0", code == 0, out[-500:])
    record("reported as a recurrence", "recurrence" in out, out[-400:])
    props = list((cwd / "records" / "skill-proposal").glob("*.md"))
    record("no second prop- file", len(props) == 1, str([p.name for p in props]))
    if props:
        record("recurrences bumped to 1",
               "recurrences: 1" in props[0].read_text(encoding="utf-8"))

    # ---- indexes --------------------------------------------------------
    print("\n[step] list and audit")
    code, out = outbox(cwd, "list")
    record("list exits 0", code == 0, out[-300:])
    record("list shows both records", "prob-0001" in out and "prop-0001" in out, out[-400:])
    code, out = outbox(cwd, "audit")
    record("audit clean", code == 0, out[-900:])
    manifest = (cwd / "MANIFEST.md").read_text(encoding="utf-8")
    record("MANIFEST lists prob-0001", "prob-0001" in manifest)
    record("MANIFEST lists prop-0001", "prop-0001" in manifest)
    idx = [json.loads(l) for l in (cwd / "index.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    record("index.jsonl has 2 entries", len(idx) == 2, str(len(idx)))
    record("index entries carry path", all("path" in e for e in idx))

    # ---- receipt loop ---------------------------------------------------
    print("\n[step] answer + sync-inbox")
    code, out = outbox(cwd, "answer", "prob-0001", "--status", "answered",
                       "--note", "set simOutputFormat=psfxl and re-run")
    record("answer exits 0", code == 0, out[-300:])
    receipt = cwd / "inbox" / "prob-0001.md"
    record("receipt written", receipt.is_file())
    code, out = outbox(cwd, "sync-inbox")
    record("sync-inbox exits 0", code == 0, out[-500:])
    record("sync-inbox reported the merge", "prob-0001 -> answered" in out, out[-400:])
    filed = next(iter((cwd / "records" / "problem").glob("*prob-0001*.md")), None)
    if filed:
        txt = filed.read_text(encoding="utf-8")
        record("record status now answered", "status: answered" in txt)
        record("receipt appended to the record", "外网回执" in txt and "psfxl" in txt)
    record("receipt moved to _done", (cwd / "inbox" / "_done" / "prob-0001.md").is_file())
    record("inbox emptied", not list((cwd / "inbox").glob("*.md")))
    code, out = outbox(cwd, "audit")
    record("audit still clean after merge", code == 0, out[-700:])

    # ---- carry-out ------------------------------------------------------
    print("\n[step] bundle")
    code, out = outbox(cwd, "bundle")
    record("bundle exits 0", code == 0, out[-900:])
    bundles = list(cwd.parent.glob("outbox-*.bundle"))
    record("bundle file produced", len(bundles) == 1, str(bundles))
    if bundles:
        record("bundle is non-trivial", bundles[0].stat().st_size > 1000,
               str(bundles[0].stat().st_size))
        code2, out2 = git(cwd, "ls-files")
        record("git ls-files succeeded", code2 == 0, out2[-300:])
        record("_local not tracked by git", "_local/" not in out2, out2[-400:])
        record("drafts not tracked by git", "drafts/" not in out2, out2[-400:])
        record("records tracked by git", "records/problem/" in out2, out2[-400:])
        record("MANIFEST tracked by git", "MANIFEST.md" in out2, out2[-400:])

    # ---- summary --------------------------------------------------------
    failed = [r for r in results if not r[1]]
    print(f"\n{'=' * 62}")
    print(f"total {len(results)} checks, {len(results) - len(failed)} ok, {len(failed)} FAIL")
    for label, _, detail in failed:
        print(f"  FAIL {label}\n       {detail[:300]}")
    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"[info] temp tree removed ({tmp})")
    else:
        print(f"[info] temp tree kept: {cwd}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
