# -*- coding: utf-8 -*-
"""tokspeed — Qoder 每回合末尾一行 token 速度统计。

数据源（纯标准库，只读）：
- 事件日志 ~/.qoder-cn/logs/sessions/<项目目录>/<会话id>/segments/<run>.jsonl
  （model.request.started / model.response.completed，ts / turn_id / request_id）
- 会话 jsonl ~/.qoder-cn/projects/<项目目录>/<会话id>.jsonl
  （assistant 行 message.usage + request_id）
- 子智能体转录 ~/.qoder-cn/projects/<项目目录>/<会话id>/subagents/agent-a*.jsonl
  （子智能体请求的 usage 只落这里，父会话 jsonl 不含；按 request_id 并进统计）

口径：默认统计「最新 turn_id」内已完成的模型请求；正在生成的末条回复天然不计。
只有 provider=custom 等真实上报 usage 的通道进 TPS / 缓存 / 用量；
无上报的请求只进耗时与计数，绝不显示为 0。
主会话与子智能体分开统计（用户裁定 2026-09-26，二次改成分行板书）：
    tok/s: 主 125 req · 35.8 tok/s · out 125.0k · 3494.5s · cache 90.5% · 19.070M
    tok/s: 子 mimo-v2.6-flash×151 · 59.0 tok/s · out 153.2k · 2598.0s · cache 90.0% · 3.106M
—— 主行只算主会话请求，子行按模型逐行列（`turn_id == session_id` 的请求），
    每行的 tok/s / out / 耗时 / cache / 用量都是该模型自己的；没有子智能体时只出主行且不带「主」字。
主行单模型不再列 models（避免把主模型速度重复一遍）；主行多模型、或整行无上报时才列。
子行没有「合计」——不同模型的混合速度没有意义。
模型名优先显示花名册（smart-subagent roster.yml）别名：UUID 形态的 ref 换成别名，映射不到保持原文。
"""
import json
import os
import re
import sys
import time
from datetime import datetime

USAGE_KEYS = ("input_tokens", "cache_read_input_tokens",
              "cache_creation_input_tokens", "output_tokens")
NO_REPORT_LABEL = "无 token 上报"
NO_REPORT_SHORT = "无上报"
MAIN_LABEL = "主"
SUB_LABEL = "子"
UNKNOWN_MODEL_LABEL = "未标注"


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


def load_subagent_usages(sub_dir, wanted=None):
    """从会话的 subagents/ 转录补 usage。

    子智能体请求的 message.usage 只落在 `projects/<proj>/<sid>/subagents/agent-a*.jsonl`，
    父会话 jsonl 不含——尾行此前对子智能体一律「无上报」，这里把真值补回来。
    `wanted` 为需要的 request_id 集合（None = 全收）。
    """
    merged = {}
    if not os.path.isdir(sub_dir):
        return merged
    for name in sorted(os.listdir(sub_dir)):
        if not name.endswith(".jsonl"):
            continue
        try:
            with open(os.path.join(sub_dir, name), "r",
                      encoding="utf-8", errors="replace") as f:
                for rid, u in load_usage_lines(f).items():
                    if wanted is not None and rid not in wanted:
                        continue
                    merged.setdefault(rid, u)
        except OSError:
            continue
    return merged


def merge_missing(base_map, extra_map):
    """把 extra_map 里 base 没有的键并入 base（同键以 base 为准），就地改并返回 base。"""
    for rid, u in extra_map.items():
        base_map.setdefault(rid, u)
    return base_map


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


def completed_in_turn(events, turn_id=None, session_id=None, role="all"):
    """返回 [(request_id, 耗时秒)]：本回合窗口内 started 与 completed 配对成功的请求。

    窗口 = 选定回合起点（该 turn 最早事件 ts）之后 started 的**全部**请求，
    started 早于窗口的上一回合拖尾请求不计。
    `role`：`all` 主会话 + 子智能体；`main` 只要主会话；`sub` 只要子智能体
    （子智能体回合的 `turn_id == session_id`，2026-09-23 实测）。
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

    def belongs(e, subagent, same_turn):
        if role == "sub":
            return subagent
        if role == "main":
            return same_turn and not subagent
        return same_turn or subagent

    starts = {}
    for e in events:
        if e.get("type") == "model.request.started" and e.get("request_id"):
            t = _parse_ts(e["ts"])
            subagent = session_id is not None and e.get("turn_id") == session_id
            same_turn = e.get("turn_id") == turn_id
            if belongs(e, subagent, same_turn) and t >= win_start:
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


# ---------- 花名册映射（显示名） ----------

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                      r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def parse_roster_aliases(text):
    """迷你扫描花名册 YAML：只抠 models 段的 (alias, ref)，不依赖 PyYAML。"""
    pairs = []
    in_models = False
    cur = None

    def flush():
        if cur and cur.get("alias"):
            pairs.append((cur["alias"], cur.get("ref", "")))

    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line[0].isspace():
            flush()
            cur = None
            in_models = line.strip().startswith("models:")
            continue
        if not in_models:
            continue
        s = line.strip()
        if s.startswith("- "):
            flush()
            cur = {}
            s = s[2:].strip()
        if cur is None:
            continue
        m = re.match(r"^(alias|ref):\s*(.+?)\s*$", s)
        if m:
            cur[m.group(1)] = m.group(2).strip("\"'")
    flush()
    return pairs


def build_alias_map(pairs):
    """[(alias, ref)] → {ref 小写: 别名}（BYOK 的 ref 是 UUID，查表用）。"""
    m = {}
    for alias, ref in pairs:
        if alias and ref:
            m.setdefault(ref.lower(), alias)
    return m


def load_roster_map(path):
    """读花名册文件 → 别名映射；缺失/读取失败返回 {}（显示自动退回原文）。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return build_alias_map(parse_roster_aliases(f.read()))
    except OSError:
        return {}


def roster_alias(raw, alias_map):
    """标签 → 显示名：UUID 形态的按花名册 ref 换别名，其余（含映射不到）保持原文。"""
    label = short_model(raw)
    if not label or not alias_map or not _UUID_RE.match(label):
        return label
    return alias_map.get(label.lower(), label)


def model_request_labels(events, alias_map=None):
    """request_id → 显示名：取 `request.started`/`response.completed` 的 `data.model` 短名，
    UUID 形态按花名册换别名。"""
    labels = {}
    for e in events:
        if e.get("type") in ("model.request.started", "model.response.completed") \
                and e.get("request_id"):
            raw = (e.get("data") or {}).get("model")
            if raw and e["request_id"] not in labels:
                labels[e["request_id"]] = roster_alias(raw, alias_map)
    return labels


def model_groups(events, requests, usage_map, alias_map=None):
    """[(显示名, 该模型的完整 summary)]，按次数降序、名字升序。

    每模型口径与段级一致：tok/s 只算该模型自身有 usage 的请求；无上报为 None，绝不显示 0。
    事件里查不到模型名的请求归 `未标注` 一组，不静默丢弃。
    """
    labels = model_request_labels(events, alias_map)
    grouped = {}
    for rid, dur in requests:
        grouped.setdefault(labels.get(rid) or UNKNOWN_MODEL_LABEL, []).append((rid, dur))
    rows = [(label, summarize(reqs, usage_map)) for label, reqs in grouped.items()]
    return sorted(rows, key=lambda kv: (-kv[1]["n"], kv[0]))


def model_stats(events, requests, usage_map, alias_map=None):
    """`model_groups` 的瘦视图：[(显示名, 次数, 独立 tok/s 或 None, 无上报数)]。"""
    return [(label, s["n"], s["tps"], s["n_no_usage"])
            for label, s in model_groups(events, requests, usage_map, alias_map)]



# ---------- 行格式 ----------

def _fmt_out(v):
    return "%.1fk" % (v / 1000.0) if v >= 1000 else str(v)


def _fmt_model_row(row):
    """一条模型统计 → `短名×N 12.3 tok/s`；该模型无上报则 `短名×N 无上报`。"""
    label, n, tps, n_no_usage = row
    text = "%s×%d" % (label, n)
    if tps is None:
        return text + " " + NO_REPORT_SHORT
    text += " %.1f tok/s" % tps
    if 0 < n_no_usage < n:
        text += " (%d %s)" % (n_no_usage, NO_REPORT_SHORT)
    return text


def _fmt_models(models):
    return "models: " + ", ".join(_fmt_model_row(row) for row in models)


def _no_report_tag(s):
    """段内部分请求无上报时的 `(2 无上报)` 标注；全无上报时不标（由 `无 token 上报` 表达）。"""
    return " (%d %s)" % (s["n_no_usage"], NO_REPORT_SHORT) \
        if 0 < s["n_no_usage"] < s["n"] else ""


def _metrics_parts(s):
    """除计数外的公共字段：tok/s、out、耗时、cache、M；全无上报时只给耗时。"""
    if s["tps"] is None:
        return [NO_REPORT_LABEL, "%.1fs" % s["duration_s"]]
    parts = ["%.1f tok/s" % s["tps"],
             "out %s" % _fmt_out(s["out_tokens"]),
             "%.1fs" % s["duration_s"]]
    if s["cache_rate"] is not None:
        parts.append("cache %.1f%%" % (s["cache_rate"] * 100))
    parts.append("%.3fM" % s["total_m"])
    return parts


def _segment(s, rows, label=None, fold_single_model=False):
    """一段统计文本（主会话或子智能体的某个模型）。

    `fold_single_model=True`（子行）：模型名并进计数位（`子 flash×6`），后面照常跟
    该模型自己的 tok/s / out / 耗时 / cache / 用量。
    主行（`fold_single_model=False`）：单模型**不**列 models——那等于把主模型速度重复一遍；
    只有多模型、或整段无上报（需要知道是哪个模型）时才列。
    """
    rows = rows or []
    metrics = _metrics_parts(s)
    fold = fold_single_model and len(rows) == 1
    if fold:
        count = "%s %s×%d%s" % (label, rows[0][0], s["n"], _no_report_tag(s))
        extra = []
    else:
        prefix = (label + " ") if label else ""
        count = "%s%d req%s" % (prefix, s["n"], _no_report_tag(s))
        show = len(rows) > 1 or (s["tps"] is None and len(rows) == 1)
        extra = rows if show else []
    parts = [count] + metrics
    if extra:
        parts.append(_fmt_models(extra))
    return " · ".join(parts)


def format_line(s, models=None, sub_models=None):
    """尾行文本：主会话一行；用了子智能体则每个子模型各占一行（用户裁定 2026-09-26）。

    `sub_models` = `model_groups` 的输出 [(显示名, summary)]，每行报该模型自己的
    tok/s / out / 耗时 / cache / 用量；不再给「子合计」，混合速度没有意义。
    """
    sub_lines = ["tok/s: " + _segment(ms, [(label, ms["n"], ms["tps"], ms["n_no_usage"])],
                                      label=SUB_LABEL, fold_single_model=True)
                 for label, ms in (sub_models or []) if ms["n"] > 0]
    has_main = s["n"] > 0
    if not has_main and not sub_lines:
        return "tok/s: 本回合无已完成请求"
    lines = []
    if has_main:
        lines.append("tok/s: " + _segment(s, models,
                                          label=MAIN_LABEL if sub_lines else None))
    lines.extend(sub_lines)
    return "\n".join(lines)




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
    main_reqs = completed_in_turn(events, session_id=session_id, role="main")
    sub_reqs = completed_in_turn(events, session_id=session_id, role="sub")
    usage_path = os.path.join(home, "projects", project_dir, session_id + ".jsonl")
    usage_map = load_usages(usage_path) if os.path.exists(usage_path) else {}
    # 子智能体请求的 usage 只落在 subagents/ 转录里，按 request_id 并进来
    wanted = {rid for rid, _dur in main_reqs} | {rid for rid, _dur in sub_reqs}
    sub_map = load_subagent_usages(
        os.path.join(home, "projects", project_dir, session_id, "subagents"), wanted=wanted)
    usage_map = merge_missing(usage_map, sub_map)
    roster = os.environ.get("TOKENSPEED_ROSTER") or \
        os.path.join(home, "skills", "smart-subagent", "roster.yml")
    alias_map = load_roster_map(roster)
    print(format_line(
        summarize(main_reqs, usage_map),
        models=model_stats(events, main_reqs, usage_map, alias_map=alias_map),
        sub_models=model_groups(events, sub_reqs, usage_map, alias_map=alias_map)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
