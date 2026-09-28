#!/usr/bin/env python3
"""G7-c: can qwen3.8-max-27B actually execute this skill?

Builds a minimal agent loop that mimics DSH Desktop and points it at the
ModelScope-hosted Qwen/Qwen3.8-27B -- the closest available stand-in for the
locally hosted 27B on the air-gapped box.

What is faithful to DSH:
  * tool names are DSH's lowercase ones (read / write / edit / bash), not
    Claude Code's Read / Write / Edit / Bash
  * the skill body is injected the way dsh-tool-skill does it, wrapped in
    <skill_instructions>, preceded by the "Base directory for this skill" hint
  * `write` has NO append mode, exactly like dsh-tool-fs
  * the model gets no coaching beyond the skill text

What is deliberately restricted (and therefore makes this an optimistic bound):
  * `bash` only runs `python .../outbox.py ...` plus a few read-only commands.
    A real DSH would allow anything, so a real 27B has more ways to wander.

Success criterion: a record lands in records/problem/ with status
pending-review, its placeholders all filled, and the guard passed -- achieved
without the harness intervening.

If the endpoint is unreachable or rate limited out, this prints SKIP and exits
0, per the instruction to skip the model test rather than fail the goal.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SETTINGS = Path(os.environ["USERPROFILE"]) / ".qoder-cn" / "settings.json"
PROVIDER = "qoder-custom-226e480c-387a-4ec8-ab9f-ef1c9bdbb7cf"
MODEL = "Qwen/Qwen3.8-27B"
SRC = Path(r"E:\Work\Qoder Projects\MySkills\DSH improve\outbox-recorder")
MAX_STEPS = 14
REQUEST_TIMEOUT = 300
RATE_LIMIT_BACKOFF = (35, 70, 120)

HARNESS_PREAMBLE = """You are an agent running inside DSH Desktop on an air-gapped
workstation. There is no internet access. Tools are named in lowercase.
The `write` tool replaces a whole file; it cannot append.
Work step by step. Do not explain more than one line between tool calls."""

TASK = """你在做 comparator 的 corner 仿真。ADE XL 跑到第三个 corner 之后停下，
打印 `cannot open raw file`，剩下四个 corner 一次都没跑。你已经试过重启仿真、
清掉结果目录重跑，都还是停在第三个；把 corner 顺序调换后，改成停在新的第三个。

把这件事记下来。"""


def load_endpoint() -> tuple[str, str]:
    p = json.loads(SETTINGS.read_text(encoding="utf-8"))["providers"][PROVIDER]
    return p["baseUrl"].rstrip("/"), p["apiKey"]


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read a UTF-8 text file and return its contents.",
            "parameters": {
                "type": "object",
                "properties": {"file_path": {"type": "string"}},
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Create or fully replace a UTF-8 text file. There is no append mode.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "Replace one exact occurrence of old_string with new_string in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": ["file_path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in the skill directory and return stdout+stderr.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]

ALLOWED_BASH = re.compile(
    r"^\s*(python3?|py)\s+.*outbox\.py|^\s*(dir|ls|type|cat|pwd|cd)\b", re.IGNORECASE
)


def split_command(cmd: str) -> list[str]:
    """Windows-aware split that strips the quotes shlex leaves on.

    With posix=False, shlex keeps `"C:\\path with space\\x.py"` quoted, so a
    naive `.endswith("outbox.py")` test fails on a perfectly valid command. The
    first run of this harness produced exactly that false denial, and the model
    had to work around a bug in the test rig rather than in the skill.
    """
    tokens = shlex.split(cmd, posix=os.name != "nt")
    out = []
    for t in tokens:
        if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
            t = t[1:-1]
        out.append(t)
    return out


class Sandbox:
    def __init__(self, root: Path):
        self.root = root
        self.calls: list[str] = []

    def _resolve(self, p: str) -> Path:
        path = Path(p)
        if not path.is_absolute():
            path = self.root / path
        return path.resolve()

    def inside(self, path: Path) -> bool:
        try:
            path.relative_to(self.root.resolve())
            return True
        except ValueError:
            return False

    def call(self, name: str, args: dict) -> str:
        self.calls.append(name)
        try:
            if name == "read":
                path = self._resolve(args["file_path"])
                if not self.inside(path):
                    return "[denied] path is outside the skill directory"
                if not path.exists():
                    return f"[error] no such file: {path}"
                return path.read_text(encoding="utf-8", errors="replace")
            if name == "write":
                path = self._resolve(args["file_path"])
                if not self.inside(path):
                    return "[denied] path is outside the skill directory"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(args["content"], encoding="utf-8")
                return f"[ok] wrote {len(args['content'])} chars to {path.name}"
            if name == "edit":
                path = self._resolve(args["file_path"])
                if not self.inside(path):
                    return "[denied] path is outside the skill directory"
                if not path.exists():
                    return f"[error] no such file: {path}"
                text = path.read_text(encoding="utf-8")
                old, new = args["old_string"], args["new_string"]
                n = text.count(old)
                if n == 0:
                    return "[error] old_string not found in the file"
                if n > 1:
                    return f"[error] old_string occurs {n} times; make it unique"
                path.write_text(text.replace(old, new, 1), encoding="utf-8")
                return f"[ok] edited {path.name}"
            if name == "bash":
                cmd = args["command"]
                # No shell. A prefix regex plus shell=True would still let
                # `python outbox.py; del /f /q C:\` through, so the command is
                # parsed and re-executed as an argument vector instead.
                if re.search(r"[;&|<>`$\n\r]", cmd):
                    return ("[denied] shell metacharacters are not allowed in this "
                            "sandbox; run one command with no piping or chaining")
                try:
                    argv = split_command(cmd)
                except ValueError as e:
                    return f"[error] cannot parse command: {e}"
                if not argv:
                    return "[error] empty command"
                head = Path(argv[0]).name.lower().removesuffix(".exe")
                if head in ("dir", "ls"):
                    target = self._resolve(argv[1]) if len(argv) > 1 else self.root
                    if not self.inside(target):
                        return "[denied] path is outside the skill directory"
                    if not target.exists():
                        return f"[error] no such directory: {target}"
                    entries = sorted(p.name + ("/" if p.is_dir() else "")
                                     for p in target.iterdir())
                    return "[exit 0]\n" + "\n".join(entries)
                if head in ("type", "cat"):
                    return self.call("read", {"file_path": argv[1] if len(argv) > 1 else ""})
                if head in ("pwd", "cd"):
                    return f"[exit 0]\n{self.root}"
                if head not in ("python", "python3", "py"):
                    return ("[denied] this sandbox only allows `python ... outbox.py ...` "
                            "and read-only listing commands")
                script = next((a for a in argv[1:] if a.replace("\\", "/").endswith("outbox.py")), None)
                if script is None:
                    return "[denied] only scripts/outbox.py may be executed here"
                script_path = self._resolve(script)
                if not self.inside(script_path):
                    return "[denied] script is outside the skill directory"
                tail = argv[argv.index(script) + 1:]
                r = subprocess.run([sys.executable, str(script_path), *tail],
                                   cwd=str(self.root), capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=180)
                out = ((r.stdout or "") + (r.stderr or "")).strip()
                return f"[exit {r.returncode}]\n{out[:4000]}"
            return f"[error] unknown tool {name}"
        except Exception as e:  # noqa: BLE001
            return f"[error] {type(e).__name__}: {e}"


def chat(base: str, key: str, messages: list[dict]) -> dict:
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "max_tokens": 16384,
        "stream": False,
        "temperature": 0.2,
    }
    body = json.dumps(payload).encode("utf-8")
    for attempt, backoff in enumerate((0,) + RATE_LIMIT_BACKOFF):
        if backoff:
            print(f"    [rate-limit] backing off {backoff}s (attempt {attempt + 1})")
            time.sleep(backoff)
        req = urllib.request.Request(f"{base}/chat/completions", data=body, method="POST")
        req.add_header("Authorization", f"Bearer {key}")
        req.add_header("Content-Type", "application/json")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=REQUEST_TIMEOUT) as r:
                js = json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            if e.code == 429 and attempt < len(RATE_LIMIT_BACKOFF):
                continue
            raise RuntimeError(f"HTTP {e.code}: {raw[:300]}") from None
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"{type(e).__name__}: {e}") from None
        if not js.get("choices"):
            raise RuntimeError(f"degenerate response, choices=null: {json.dumps(js)[:200]}")
        return js


def main() -> int:
    if not SRC.exists():
        print(f"[FAIL] source tree missing: {SRC}")
        return 2
    base, key = load_endpoint()

    # reachability first, so an unreachable endpoint skips instead of failing
    try:
        probe = chat(base, key, [{"role": "user", "content": "Reply with exactly: OK"}])
        print(f"[info] endpoint reachable, probe finish_reason="
              f"{probe['choices'][0].get('finish_reason')}")
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] cannot reach {MODEL}: {e}")
        print("[skip] per instruction, the 27B model test is skipped, not failed.")
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="outbox-27b-"))
    root = tmp / "outbox-recorder"
    shutil.copytree(SRC, root, ignore=shutil.ignore_patterns("__pycache__"))
    subprocess.run([sys.executable, str(root / "scripts" / "outbox.py"), "init",
                    "--project", "comparator-tapeout"],
                   cwd=str(root), capture_output=True, text=True)
    print(f"[info] sandbox: {root}")

    skill_md = (root / "SKILL.md").read_text(encoding="utf-8")
    body = skill_md.split("---", 2)[2].strip()
    system = (
        HARNESS_PREAMBLE + "\n\n"
        f"Base directory for this skill: {root}\n"
        "Resolve relative paths mentioned by this skill against the base directory "
        "before using them. Load referenced resources only as needed.\n\n"
        "<skill_instructions>\n" + body + "\n</skill_instructions>"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": TASK},
    ]
    sandbox = Sandbox(root)
    transcript: list[dict] = []
    finish = "max_steps"

    for step in range(1, MAX_STEPS + 1):
        t0 = time.time()
        try:
            js = chat(base, key, messages)
        except Exception as e:  # noqa: BLE001
            print(f"[SKIP] request failed at step {step}: {e}")
            print("[skip] per instruction, the 27B model test is skipped, not failed.")
            shutil.rmtree(tmp, ignore_errors=True)
            return 0
        msg = js["choices"][0]["message"]
        usage = js.get("usage") or {}
        content = (msg.get("content") or "").strip()
        calls = msg.get("tool_calls") or []
        reasoning = msg.get("reasoning_content") or ""
        print(f"\n--- step {step}  ({time.time()-t0:.0f}s, "
              f"prompt={usage.get('prompt_tokens')}, completion={usage.get('completion_tokens')}, "
              f"reasoning_chars={len(reasoning)}) ---")
        if content:
            print(f"  model: {content[:600]}")
        transcript.append({"step": step, "content": content,
                           "tools": [c["function"]["name"] for c in calls],
                           "reasoning_chars": len(reasoning),
                           "usage": usage})
        messages.append({"role": "assistant", "content": msg.get("content"),
                         "tool_calls": calls or None})
        if not calls:
            finish = "no_tool_call"
            break
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError as e:
                args = {}
                result = f"[error] arguments were not valid JSON: {e}"
            else:
                brief = args.get("command") or args.get("file_path") or ""
                print(f"  -> {name} {str(brief)[:160]}")
                result = sandbox.call(name, args)
                first = result.splitlines()[0] if result else ""
                print(f"     {first[:200]}")
            messages.append({"role": "tool", "tool_call_id": c.get("id"), "content": result})

    # ---- judge -----------------------------------------------------------
    print("\n" + "=" * 62)
    problems = list((root / "records" / "problem").glob("*.md")) if (root / "records" / "problem").exists() else []
    checks: list[tuple[str, bool, str]] = []

    def ck(label, ok, detail=""):
        checks.append((label, bool(ok), detail))
        print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f" -- {detail}" if detail and not ok else ""))

    print("[judge] did the 27B model complete the three-step protocol unaided?")
    ck("a record was filed under records/problem/", len(problems) == 1,
       f"found {len(problems)}: {[p.name for p in problems]}")
    ck("tool sequence used bash (not hand-written files)", "bash" in sandbox.calls,
       str(sandbox.calls))
    ck("model never used write to fabricate a record",
       not any(c == "write" for c in sandbox.calls), str(sandbox.calls))
    ck("loop ended because the model stopped calling tools", finish == "no_tool_call",
       f"finish={finish}, steps={len(transcript)}")

    if problems:
        text = problems[0].read_text(encoding="utf-8")
        ck("status is pending-review", "status: pending-review" in text)
        ck("id was assigned by the script", re.search(r"id: prob-\d{4}", text) is not None)
        ck("no placeholder survived", "{{" not in text)
        ck("severity was chosen", re.search(r"severity: (blocking|slowing|annoyance)", text) is not None,
           [l for l in text.splitlines() if l.startswith("severity")].__str__())
        ck("project stamped", "project: comparator-tapeout" in text)
        ck("the 期望的答案长什么样 section has real content",
           len(re.split(r"##\s*期望的答案长什么样\s*\n", text)[-1].split("##")[0].strip()) > 30)
        ck("the observed error string made it into the record",
           "cannot open raw file" in text)
        ck("record is under the 200-line budget", len(text.splitlines()) <= 200,
           f"{len(text.splitlines())} lines")
        r = subprocess.run(
            [sys.executable, str(root / "scripts" / "outbox.py"), "audit"],
            cwd=str(root), capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        ck("audit passes on what the model produced", r.returncode == 0,
           ((r.stdout or "") + (r.stderr or ""))[-500:])

    failed = [c for c in checks if not c[1]]
    print(f"\ntotal {len(checks)} checks, {len(checks) - len(failed)} ok, {len(failed)} FAIL")
    print(f"tool calls: {sandbox.calls}")
    print(f"steps used: {len(transcript)} / {MAX_STEPS}")

    report = tmp.parent / f"outbox-27b-transcript-{time.strftime('%Y%m%d-%H%M%S')}.json"
    report.write_text(json.dumps({
        "model": MODEL, "finish": finish, "steps": transcript,
        "tool_calls": sandbox.calls,
        "checks": [{"label": l, "ok": o, "detail": d} for l, o, d in checks],
        "record": problems[0].read_text(encoding="utf-8") if problems else None,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[info] transcript -> {report}")
    print(f"[info] sandbox kept at {root} (delete manually if not needed)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
