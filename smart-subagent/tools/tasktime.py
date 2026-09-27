# -*- coding: utf-8 -*-
"""汇总 Qoder 会话里各子 Agent 任务的真实墙钟耗时（只读，纯标准库）。

用法：python tasktime.py [--session-dir DIR] [--home DIR]

数据源：<session-dir>/subagents/task-*.json 的 createdAt/updatedAt/completedAt；
缺时间戳时退回 transcriptPath 指向的 jsonl 首末 timestamp 差。
"""

import glob
import json
import os
import re
import sys
from datetime import datetime

USAGE = "usage: python tasktime.py [--session-dir DIR] [--home DIR]"


def _reconfigure(stream):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass


_reconfigure(sys.stdout)
_reconfigure(sys.stderr)


class _UsageError(Exception):
    """命令行参数错误。"""


class _InputError(Exception):
    """输入数据错误（目录不存在、json 解析失败等）。"""


def _parse_args(argv):
    opts = {"session_dir": None, "home": None, "help": False}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            opts["help"] = True
            i += 1
        elif arg in ("--session-dir", "--home"):
            if i + 1 >= len(argv):
                raise _UsageError("%s: expected one argument" % arg)
            key = "session_dir" if arg == "--session-dir" else "home"
            opts[key] = argv[i + 1]
            i += 2
        else:
            raise _UsageError("unknown argument: %s" % arg)
    return opts


def _default_home():
    return os.environ.get("QODER_CN_HOME") or os.path.expanduser("~/.qoder-cn")


def _newest_session_dir(home):
    """在 <home>/projects/*/*/subagents/task-*.json 中取 mtime 最新的一组。"""
    pattern = os.path.join(home, "projects", "*", "*", "subagents", "task-*.json")
    groups = {}
    for path in glob.glob(pattern):
        groups.setdefault(os.path.dirname(path), []).append(path)
    if not groups:
        return None
    best_dir, best_mtime = None, -1.0
    for dirpath, files in groups.items():
        newest = max(os.path.getmtime(f) for f in files)
        if newest > best_mtime:
            best_dir, best_mtime = dirpath, newest
    return os.path.dirname(best_dir)


def _to_epoch(text):
    """ISO 8601（形如 2026-09-26T15:41:01.472Z）→ epoch 秒；失败返回 None。"""
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return datetime.fromisoformat(text.strip().replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _transcript_span(path):
    """transcript jsonl 所有行 timestamp 的首末差（秒）；拿不到返回 None。"""
    if not path or not os.path.isfile(path):
        return None
    stamps = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    ts = obj.get("timestamp")
                    if isinstance(ts, str) and ts.strip():
                        stamps.append(ts)
    except OSError:
        return None
    if len(stamps) < 2:
        return None
    first, last = _to_epoch(stamps[0]), _to_epoch(stamps[-1])
    if first is None or last is None:
        return None
    return last - first


def _load_tasks(session_dir):
    """读取 <session-dir>/subagents/task-*.json，返回任务字典列表。"""
    sub = os.path.join(session_dir, "subagents")
    pattern = os.path.join(sub, "task-*.json")
    files = sorted(glob.glob(pattern))
    tasks = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
        except (ValueError, OSError) as exc:
            raise _InputError("failed to parse %s: %s" % (path, exc))
        if not isinstance(data, dict):
            raise _InputError("failed to parse %s: not a json object" % path)
        data["_file"] = os.path.basename(path)
        tasks.append(data)
    return tasks


def _row(task):
    """计算单个任务的 (createdAt 排序键, invName, 状态, 墙钟文本, 来源, 描述)。"""
    created = task.get("createdAt")
    end = task.get("completedAt") or task.get("updatedAt")
    duration = None
    source = "missing"
    if isinstance(created, (int, float)) and isinstance(end, (int, float)) and created:
        duration = (end - created) / 1000.0
        source = "task-json"
    else:
        span = _transcript_span(task.get("transcriptPath"))
        if span is not None:
            duration = span
            source = "transcript"
    wall = "%.1fs" % duration if duration is not None else "?s"
    inv = str(task.get("invocationName") or task.get("_file")[:-5])
    status = str(task.get("status") or "?")
    desc = re.sub(r"\s+", " ", str(task.get("description") or "")).strip()
    order = created if isinstance(created, (int, float)) else None
    return order, inv, status, wall, source, desc, duration, task["_file"]


def _render(tasks):
    rows = [_row(t) for t in tasks]
    ready = [r for r in rows if r[0] is not None]
    tail = sorted([r for r in rows if r[0] is None], key=lambda r: r[7])
    ready.sort(key=lambda r: (r[0], r[7]))
    ordered = ready + tail

    lines = ["  ".join(part for part in (r[1], r[2], r[3], r[4], r[5]) if part is not None).rstrip()
             for r in ordered]

    count = len(ordered)
    completed = sum(1 for t in tasks if t.get("status") == "completed")
    total = sum(r[6] for r in ordered if r[6] is not None)
    starts = [t.get("createdAt") for t in tasks if isinstance(t.get("createdAt"), (int, float))]
    ends = []
    for t in tasks:
        end = t.get("completedAt") or t.get("updatedAt")
        if isinstance(end, (int, float)):
            ends.append(end)
    if starts and ends:
        span = "%.1f" % ((max(ends) - min(starts)) / 1000.0)
    else:
        span = "?"
    lines.append(
        "total  %d 个 · 完成 %d 个 · sum %.1fs · span %ss"
        % (count, completed, total, span)
    )
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        opts = _parse_args(argv)
    except _UsageError as exc:
        print("%s\n%s" % (exc, USAGE), file=sys.stderr)
        return 3
    if opts["help"]:
        print(USAGE)
        return 0

    session_dir = opts["session_dir"]
    if session_dir is None:
        session_dir = _newest_session_dir(opts["home"] or _default_home())
        if session_dir is None:
            print("no subagent tasks found")
            return 0
    elif not os.path.isdir(session_dir):
        print("session dir not found: %s" % session_dir, file=sys.stderr)
        return 3

    try:
        tasks = _load_tasks(session_dir)
    except _InputError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    if not tasks:
        print("no subagent tasks found")
        return 0
    print(_render(tasks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
