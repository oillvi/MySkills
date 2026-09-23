# -*- coding: utf-8 -*-
"""tokspeed — Qoder 每回合末尾一行 token 速度统计。

数据源（纯标准库，只读）：
- 事件日志 ~/.qoder-cn/logs/sessions/<项目目录>/<会话id>/segments/<run>.jsonl
  （model.request.started / model.response.completed，ts / turn_id / request_id）
- 会话 jsonl ~/.qoder-cn/projects/<项目目录>/<会话id>.jsonl
  （assistant 行 message.usage + request_id）

口径：默认统计「最新 turn_id」内已完成的模型请求；正在生成的末条回复天然不计。
只有 provider=custom 等真实上报 usage 的通道进 TPS / 缓存 / 用量；
无上报的请求只进耗时与计数，绝不显示为 0。
"""
import json
import os
import sys
import time
from datetime import datetime

USAGE_KEYS = ("input_tokens", "cache_read_input_tokens",
              "cache_creation_input_tokens", "output_tokens")
NO_REPORT_LABEL = "无 token 上报"
TAIL_NOTE = "末条回复不计"


# ---------- 解析 ----------

def load_events_lines(lines):
    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


def load_events(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return load_events_lines(f)


def load_usage_lines(lines):
    usages = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        message = obj.get("message") or {}
        usage = message.get("usage")
        # 真实 jsonl 里 request_id 在 message.usage 内部；其余位置是兜底
        rid = None
        if isinstance(usage, dict):
            rid = usage.get("request_id")
        rid = rid or message.get("request_id") or obj.get("request_id")
        if rid and isinstance(usage, dict):
            usages[rid] = usage
    return usages


def load_usages(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return load_usage_lines(f)


# ---------- 回合窗口与配对 ----------

def _parse_ts(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def current_turn_id(events, session_id=None):
    """当前主会话回合：turn_id 是 UUID，取「时间上最后开始」的回合。

    `turn_id == session_id` 的是后台子智能体回合（2026-09-23 实测：glm-scout 派单
    回合的 turn_id 就是会话 id），一律排除；全部被排除时退回不过滤。
    """
    candidates = [e for e in events
                  if e.get("type") == "model.request.started"
                  and e.get("turn_id") is not None and e.get("request_id")]
    if not candidates:
        return None
    main = [e for e in candidates if e.get("turn_id") != session_id] or candidates
    latest = max(main, key=lambda e: (_parse_ts(e["ts"]), e.get("seq") or 0))
    return latest.get("turn_id")


def completed_in_turn(events, turn_id=None, session_id=None):
    """返回 [(request_id, 耗时秒)]：本回合窗口内 started 与 completed 配对成功的请求。

    窗口 = 选定回合起点（该 turn 最早事件 ts）之后 started 的**全部**请求，
    含子智能体回合（turn_id == session_id，用户裁定 2026-09-23 纳入）；
    started 早于窗口的上一回合拖尾请求不计。
    """
    if turn_id is None:
        turn_id = current_turn_id(events, session_id)
        if turn_id is None:
            return []
    turn_ts = [_parse_ts(e["ts"]) for e in events
               if e.get("turn_id") == turn_id and e.get("ts")]
    if not turn_ts:
        return []
    win_start = min(turn_ts)
    starts = {}
    for e in events:
        if e.get("type") == "model.request.started" and e.get("request_id"):
            t = _parse_ts(e["ts"])
            same_turn = e.get("turn_id") == turn_id
            subagent = session_id is not None and e.get("turn_id") == session_id
            if (same_turn or subagent) and t >= win_start:
                # attempt_failed 后重试会再次 started：耗时从第一次算（请求总墙钟）
                starts.setdefault(e["request_id"], t)
    done = []
    for e in events:
        if e.get("type") == "model.response.completed":
            rid = e.get("request_id")
            if rid in starts:
                dur = (_parse_ts(e["ts"]) - starts[rid]).total_seconds()
                done.append((rid, dur))
    return done


# ---------- 统计 ----------

def _is_real_usage(u):
    return isinstance(u, dict) and any(u.get(k, 0) for k in USAGE_KEYS)


def summarize(requests, usage_map):
    s = {
        "n": len(requests),
        "n_no_usage": 0,
        "tps": None,
        "duration_s": 0.0,
        "out_tokens": 0,
        "cache_rate": None,
        "total_m": 0.0,
    }
    sum_dur_all = 0.0
    sum_dur_used = 0.0
    sum_input = 0
    sum_cread = 0
    sum_ccreate = 0
    sum_out = 0
    for rid, dur in requests:
        sum_dur_all += dur
        u = usage_map.get(rid)
        if not _is_real_usage(u):
            s["n_no_usage"] += 1
            continue
        sum_dur_used += dur
        sum_input += u.get("input_tokens", 0) or 0
        sum_cread += u.get("cache_read_input_tokens", 0) or 0
        sum_ccreate += u.get("cache_creation_input_tokens", 0) or 0
        sum_out += u.get("output_tokens", 0) or 0
    s["duration_s"] = sum_dur_all
    s["out_tokens"] = sum_out
    if sum_dur_used > 0:
        s["tps"] = sum_out / sum_dur_used
        s["total_m"] = (sum_input + sum_ccreate + sum_out) / 1e6
        if sum_input > 0:
            s["cache_rate"] = sum_cread / sum_input
    return s


# ---------- 模型归属 ----------

def short_model(raw):
    raw = str(raw or "")
    return raw.rsplit("/", 1)[-1] if raw else ""


def model_counts(events, request_ids):
    """[(短模型名, 次数)]，按次数降序、名字升序；模型名取 request.started 的 data.model。"""
    labels = {}
    for e in events:
        if e.get("type") in ("model.request.started", "model.response.completed") \
                and e.get("request_id"):
            raw = (e.get("data") or {}).get("model")
            if raw and e["request_id"] not in labels:
                labels[e["request_id"]] = short_model(raw)
    counter = {}
    for rid in request_ids:
        label = labels.get(rid)
        if label:
            counter[label] = counter.get(label, 0) + 1
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


# ---------- 行格式 ----------

def _fmt_out(v):
    return "%.1fk" % (v / 1000.0) if v >= 1000 else str(v)


def format_line(s, models=None):
    if s["n"] == 0:
        return "tok/s: 本回合无已完成请求 · %s" % TAIL_NOTE
    model_part = ""
    if models:
        model_part = " · models: " + ", ".join("%s×%d" % (label, c) for label, c in models)
    na = " (%d 无上报)" % s["n_no_usage"] if 0 < s["n_no_usage"] < s["n"] else ""
    if s["tps"] is None:
        return "tok/s: %d req%s · %s · %.1fs%s · %s" % (
            s["n"], na, NO_REPORT_LABEL, s["duration_s"], model_part, TAIL_NOTE)
    parts = [
        "tok/s: %d req%s" % (s["n"], na),
        "%.1f tok/s" % s["tps"],
        "out %s" % _fmt_out(s["out_tokens"]),
        "%.1fs" % s["duration_s"],
    ]
    if s["cache_rate"] is not None:
        parts.append("cache %.1f%%" % (s["cache_rate"] * 100))
    parts.append("%.3fM" % s["total_m"])
    if models:
        parts.append("models: " + ", ".join("%s×%d" % (label, c) for label, c in models))
    parts.append(TAIL_NOTE)
    return " · ".join(parts)


# ---------- 日志定位 ----------

def _anchor_ts(path, anchor):
    """segment 内最近一次「真正执行了 anchor 命令」的 tool.shell.started/tool.requested 时间。"""
    latest = None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if anchor not in line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if o.get("type") not in ("tool.shell.started", "tool.requested"):
                    continue
                data = o.get("data") or {}
                command = data.get("command") or (data.get("args") or {}).get("command")
                if not isinstance(command, str) or anchor not in command:
                    continue
                ts_raw = o.get("ts")
                if ts_raw:
                    latest = max(latest or "", ts_raw)
    except OSError:
        return None
    return latest


def latest_segment(sessions_root, anchor="tokspeed.py", now=None, scan_window=300):
    """定位「当前会话」的 segment。

    多会话并发时 mtime 最新不一定是自己（2026-09-23 实测被并行会话抢走）；
    近 `scan_window` 秒活跃的 segment 里，找最近一条 shell 命令文本含 `anchor`
    的那个 = 正在运行本脚本的会话（调用命令里必然含 tokspeed.py）。找不到再退回 mtime 最新。
    """
    files = []
    for dirpath, _dirnames, filenames in os.walk(sessions_root):
        if os.path.basename(dirpath) != "segments":
            continue
        for name in filenames:
            if name.endswith(".jsonl"):
                p = os.path.join(dirpath, name)
                files.append((p, os.path.getmtime(p)))
    if not files:
        return None
    if anchor:
        now = time.time() if now is None else now
        best, best_ts = None, None
        for p, mtime in files:
            if now - mtime > scan_window:
                continue
            hit = _anchor_ts(p, anchor)
            if hit and (best_ts is None or hit > best_ts):
                best, best_ts = p, hit
        if best:
            return best
    return max(files, key=lambda kv: kv[1])[0]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    home = os.environ.get("QODER_CN_HOME") or os.path.expanduser("~/.qoder-cn")
    sessions_root = os.path.join(home, "logs", "sessions")
    segment = latest_segment(sessions_root)
    if not segment:
        print("tok/s: 未找到会话事件日志")
        return 1
    parts = os.path.normpath(segment).split(os.sep)
    # .../sessions/<项目目录>/<会话id>/segments/<run>.jsonl
    project_dir, session_id = parts[-4], parts[-3]
    events = load_events(segment)
    requests = completed_in_turn(events, session_id=session_id)
    usage_path = os.path.join(home, "projects", project_dir, session_id + ".jsonl")
    usage_map = load_usages(usage_path) if os.path.exists(usage_path) else {}
    models = model_counts(events, [rid for rid, _dur in requests])
    print(format_line(summarize(requests, usage_map), models=models))
    return 0


if __name__ == "__main__":
    sys.exit(main())
