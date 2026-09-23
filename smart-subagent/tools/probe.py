#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看守探针 v0（watchdog probe）——只读、纯标准库、输出 ≤10 行 digest。

用法:
    python tools/probe.py <transcript.jsonl> [--budget N] [--window N]
                          [--fine coder|scout] [--expect STR] [--expect-file PATH]

细探针（--fine，纯加法，不传则输出/exit 与 v0 完全一致）:
    coder: C1 同路径 Write/Edit/NotebookEdit 按逻辑轮 ≥3=WARN ≥5=BLOCK
           C2 (需 --expect) Bash/shell 命令含子串，0=WARN ≥1=正常行
           C3 (需 --expect-file) 交付物被写过或已存在，否则 WARN
    scout: S1 Grep/Glob 同 pattern ≥3=WARN ≥5=BLOCK
           S2 窗口近5轮 Read≥3 且全是旧路径 = WARN
           S3 同路径 Read ≥3=WARN ≥5=BLOCK

参数口径:
    --budget N  输出 token 预算，口径 = transcript 各行 message.usage.output_tokens
                之和（文档未写死，按此口径）；达到 80% WARN、100% BLOCK；不传则不检测预算。
    --window N  检测滑窗条数：只在最近 N 条事件上做模式判定（默认 20，
                依据 reference/watchdog.md §2「最近事件窗口 20 条」）；
                停滞与预算按全文件统计，不吃窗口。

判据阈值照抄 reference/watchdog.md §2 判据表（不做标定）:
    repeat(同工具同参数全等重复)   WARN 2 次  / BLOCK 3 次
    fuzzy(近似重复指纹,防微循环)   WARN 3 次  / BLOCK 5 次
    alternating(A-B-A-B 交替振荡)  WARN 3 轮  / BLOCK 6 轮
    error(连续报错不收敛)          WARN 2 次  / BLOCK 3 次
    monologue(连续独白无工具产出)  WARN 2 条  / BLOCK 3 条
    context_error(context 错误)    WARN 2 次  / BLOCK 3 次（§2 未单列，比照 error）
    stall(事件停滞无新事件)        WARN 90s   / BLOCK 300s
    budget(步数/预算)              WARN 80%   / BLOCK 100%

输出: 首行 状态+命中信号名；每条命中一行计数证据；末行处置建议。
退出码: 0=OK  1=WARN  2=BLOCK  3=输入错误。
纯只读，不写任何文件。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

TH = {
    "repeat": (2, 3),
    "fuzzy": (3, 5),
    "alternating": (3, 6),
    "error": (2, 3),
    "monologue": (2, 3),
    "context_error": (2, 3),
    "stall": (90, 300),
}

# transcript 末行属于这些类型 = 会话已收尾，不再按墙钟判停滞
TERMINAL_LAST_TYPES = ("last-prompt", "result", "summary")

CTX_RE = re.compile(
    r"context (length|window|limit)|maximum context|context.{0,20}exceed"
    r"|too many tokens|token limit|input is too long",
    re.IGNORECASE,
)

DEFAULT_WINDOW = 20

WRITE_TOOLS = ("Write", "Edit", "NotebookEdit")


def _fp_parts(fp):
    """canon 指纹 'name|json' → (name, input dict)。"""
    name, _, body = fp.partition("|")
    try:
        inp = json.loads(body)
    except ValueError:
        inp = {}
    if not isinstance(inp, dict):
        inp = {}
    return name, inp


def _fine(name, level, count, warn, block, detail, no_th=False):
    return {"name": name, "level": level, "count": count,
            "warn": warn, "block": block, "detail": detail, "no_th": no_th}


def _canon(name, inp):
    """工具调用的全等指纹：name + 规范化 input JSON。"""
    try:
        body = json.dumps(inp if inp is not None else {}, sort_keys=True,
                          ensure_ascii=False)
    except (TypeError, ValueError):
        body = repr(inp)
    return "%s|%s" % (name or "", body)


def _bigrams(s):
    return set(s[i:i + 2] for i in range(len(s) - 1)) or ({s} if s else set())


def _parse_ts(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _jaccard(a, b):
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def _max_run(seq, key=lambda x: x):
    best = cur = 0
    prev = object()
    for item in seq:
        k = key(item)
        cur = cur + 1 if cur and k == prev else 1
        prev = k
        best = max(best, cur)
    return best


def _alternating_rounds(acts):
    """A-B-A-B 交替 run 的最大轮数（一轮 = 一对 A,B）。"""
    best = i = 0
    n = len(acts)
    while i + 1 < n:
        if acts[i] != acts[i + 1]:
            a, b = acts[i], acts[i + 1]
            length, j = 2, i + 2
            while j < n and acts[j] == (a if (j - i) % 2 == 0 else b):
                length += 1
                j += 1
            best = max(best, length // 2)
            i = max(j, i + 1)
        else:
            i += 1
    return best


def _fuzzy_cluster(acts):
    """近似重复指纹最大簇：Jaccard∈[0.8,1.0) 的二元组并查集（全等归 repeat）。"""
    n = len(acts)
    par = list(range(n))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    bgs = [_bigrams(a) for a in acts]
    for i in range(n):
        for j in range(i + 1, n):
            if acts[i] == acts[j]:
                continue  # 全等重复由 repeat 信号负责
            A, B = bgs[i], bgs[j]
            if not A or not B:
                continue
            if len(A & B) / len(A | B) >= 0.8:
                ri, rj = find(i), find(j)
                if ri != rj:
                    par[ri] = rj
    if not n:
        return 0
    counts = {}
    for i in range(n):
        r = find(i)
        counts[r] = counts.get(r, 0) + 1
    return max(counts.values())


def analyze_text(text, window=DEFAULT_WINDOW, budget=None, now=None,
                 fine=None, expect=None, expect_file=None):
    """解析 transcript 文本并判定。返回 dict(status, hits, tokens, last_ts, n_lines)。

    合成/真实 jsonl 均走此函数；window 只作用于模式类信号，
    stall/budget 按全文件统计。
    """
    events = []          # ('assistant',[fps],ts) / ('result',sub,ts) / ('reset',None,ts)
    tokens = 0
    ctx_bad = 0          # 解析不成功的行 = context 损坏
    last_type = None
    last_ts = None
    n_lines = 0
    turn_fps = []        # 同一轮 = 连续 assistant 行（thinking/text/tool_use 可分行落盘）
    turn_ts = None
    turn_open = False

    def flush_turn():
        nonlocal turn_fps, turn_ts, turn_open
        if turn_open:
            events.append(("assistant", turn_fps, turn_ts))
            turn_fps, turn_ts, turn_open = [], None, False

    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        n_lines += 1
        try:
            d = json.loads(raw)
            if not isinstance(d, dict):
                raise ValueError("not an object")
        except (ValueError, TypeError):
            ctx_bad += 1
            flush_turn()
            continue
        last_type = d.get("type")
        ts = _parse_ts(d.get("timestamp"))
        if ts is not None:
            last_ts = ts
        msg = d.get("message") or {}
        if not isinstance(msg, dict):
            msg = {}
        usage = msg.get("usage")
        if isinstance(usage, dict):
            try:
                tokens += int(usage.get("output_tokens") or 0)
            except (TypeError, ValueError):
                pass
        content = msg.get("content")
        etype = d.get("type")
        if etype == "assistant" and isinstance(content, list):
            fps = [_canon(b.get("name"), b.get("input"))
                   for b in content
                   if isinstance(b, dict) and b.get("type") == "tool_use"]
            if not turn_open:
                turn_open, turn_ts = True, ts
            turn_fps.extend(fps)      # 连续 assistant 行并入同一轮
        elif etype == "user":
            flush_turn()
            if isinstance(content, list):
                results = [b for b in content
                           if isinstance(b, dict) and b.get("type") == "tool_result"]
                for b in results:
                    is_err = bool(b.get("is_error"))
                    blob = json.dumps(b.get("content"), ensure_ascii=False)
                    if is_err and CTX_RE.search(blob):
                        sub = "ctx"
                    elif is_err:
                        sub = "err"
                    else:
                        sub = "ok"
                    events.append(("result", sub, ts))
                if not results and any(isinstance(b, dict) and b.get("type") == "text"
                                       for b in content):
                    events.append(("reset", None, ts))
            else:
                events.append(("reset", None, ts))  # 纯文本 user 指令打断独白/报错链
        else:
            flush_turn()
            events.append(("reset", None, ts))      # last-prompt 等标记行

    flush_turn()
    if n_lines == 0:
        raise ValueError("empty transcript")

    win = events[-window:] if window and window > 0 else events

    # ---- 模式类信号（滑窗内） ----
    acts = [fp for kind, payload, _ts in win if kind == "assistant" for fp in payload]
    rep_run = _max_run(acts)
    alt_rounds = _alternating_rounds(acts)
    fuzzy_size = _fuzzy_cluster(acts)

    err_run = ctx_run = 0
    max_err = max_ctx = 0
    mono_run = max_mono = 0
    for kind, payload, _ts in win:
        if kind == "result":
            if payload == "err":
                err_run += 1
                ctx_run = 0
            elif payload == "ctx":
                ctx_run += 1
                err_run = 0
            else:
                err_run = ctx_run = 0
            max_err = max(max_err, err_run)
            max_ctx = max(max_ctx, ctx_run)
        elif kind == "assistant":
            if payload:
                mono_run = 0
            else:
                mono_run += 1
                max_mono = max(max_mono, mono_run)
        elif kind == "reset":
            mono_run = 0
    max_ctx = max(max_ctx, ctx_bad)  # 解析坏行计入 context_error

    hits = []

    def add(name, count, detail):
        warn, block = TH[name]
        level = "BLOCK" if count >= block else ("WARN" if count >= warn else None)
        if level:
            hits.append({"name": name, "level": level, "count": count,
                         "warn": warn, "block": block, "detail": detail})

    add("repeat", rep_run, "连续全等重复 %d 次" % rep_run)
    add("fuzzy", fuzzy_size, "近似重复指纹簇 %d 次" % fuzzy_size)
    add("alternating", alt_rounds, "A-B 交替 %d 轮" % alt_rounds)
    add("error", max_err, "连续报错 %d 次" % max_err)
    add("monologue", max_mono, "连续独白 %d 条" % max_mono)
    add("context_error", max_ctx, "context 错误 %d 次" % max_ctx)

    # ---- 停滞（全文件；已收尾 transcript 不判） ----
    if not (last_type in TERMINAL_LAST_TYPES) and last_ts is not None:
        ref = now or datetime.now(timezone.utc)
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        age = int((ref - last_ts).total_seconds())
        if age >= 0:
            warn, block = TH["stall"]
            if age >= block or age >= warn:
                hits.append({"name": "stall",
                             "level": "BLOCK" if age >= block else "WARN",
                             "count": age, "warn": warn, "block": block,
                             "detail": "停滞 %ds" % age})

    # ---- 预算（全文件，口径=输出 token 之和） ----
    if budget is not None and budget > 0:
        ratio = tokens / budget
        if ratio >= 1.0 or ratio >= 0.8:
            hits.append({"name": "budget",
                         "level": "BLOCK" if ratio >= 1.0 else "WARN",
                         "count": tokens, "warn": 80, "block": 100,
                         "detail": "输出 token %d/%d (%.0f%%)"
                                   % (tokens, int(budget), ratio * 100)})

    fine_notes = []   # 细探针正常行：只进 digest 文本，不进 hits

    # ---- 细探针（--fine，窗口内逻辑轮=assistant 行合并，纯加法） ----
    if fine:
        win_turns = [payload
                     for i, (kind, payload, _ts) in enumerate(win)
                     if kind == "assistant"]

        def _tools(fps):
            return [_fp_parts(fp) for fp in fps]

        if fine == "coder":
            # C1 同路径 Write/Edit/NotebookEdit 按逻辑轮计数
            pr = {}
            for fps in win_turns:
                seen = set()
                for name, inp in _tools(fps):
                    if name in WRITE_TOOLS:
                        p = str(inp.get("file_path") or "")
                        if p and p not in seen:
                            seen.add(p)
                            pr[p] = pr.get(p, 0) + 1
            for p, c in sorted(pr.items(), key=lambda kv: -kv[1]):
                if c >= 3:
                    hits.append(_fine("fine[C1]", "BLOCK" if c >= 5 else "WARN",
                                      c, 3, 5, "同路径改动 %s×%d" % (p, c)))
                    break
            # C2 验收命令命中
            if expect is not None:
                n = 0
                for fps in win_turns:
                    for name, inp in _tools(fps):
                        if "Bash" in name or "shell" in name:
                            if expect in str(inp.get("command") or ""):
                                n += 1
                if n:
                    fine_notes.append(_fine("fine[C2]", "OK", n, 0, 0,
                                            "验收命令命中 ×%d" % n, no_th=True))
                else:
                    hits.append(_fine("fine[C2]", "WARN", 0, 1, 0,
                                      '验收命令未出现: "%s"' % expect, no_th=True))
            # C3 交付物
            if expect_file is not None:
                touched = any(
                    name in WRITE_TOOLS
                    and str(inp.get("file_path") or "") == expect_file
                    for fps in win_turns for name, inp in _tools(fps))
                if touched or os.path.exists(expect_file):
                    fine_notes.append(_fine("fine[C3]", "OK", 1, 0, 0,
                                            "交付物就位: %s" % expect_file, no_th=True))
                else:
                    hits.append(_fine("fine[C3]", "WARN", 0, 1, 0,
                                      "交付物缺位: %s" % expect_file, no_th=True))
        else:  # scout
            # S1 Grep/Glob 同查询计数（pattern 规范化）
            pc = {}
            for fps in win_turns:
                for name, inp in _tools(fps):
                    if name in ("Grep", "Glob"):
                        pat = re.sub(r"\s+", " ",
                                     str(inp.get("pattern") or "")).strip()
                        if pat:
                            pc[pat] = pc.get(pat, 0) + 1
            for p, c in sorted(pc.items(), key=lambda kv: -kv[1]):
                if c >= 3:
                    hits.append(_fine("fine[S1]", "BLOCK" if c >= 5 else "WARN",
                                      c, 3, 5, "同查询 %s×%d" % (p, c)))
                    break
            # S2 近5轮 Read ≥3 且 file_path 全是此前轮次（该轮之前）出现过的旧路径
            recent5 = win_turns[-5:]
            all_turns = [payload for kind, payload, _ts in events
                         if kind == "assistant"]
            start5 = len(all_turns) - len(recent5)
            turn_paths = [set(str(inp["file_path"])
                              for name, inp in _tools(fps)
                              if inp.get("file_path"))
                          for fps in all_turns]
            n_read = 0
            all_old = True
            for idx in range(start5, len(all_turns)):
                older = set().union(*turn_paths[:idx]) if idx else set()
                for name, inp in _tools(all_turns[idx]):
                    if name == "Read" and inp.get("file_path"):
                        n_read += 1
                        if str(inp["file_path"]) not in older:
                            all_old = False
            if n_read >= 3 and all_old:
                hits.append(_fine("fine[S2]", "WARN", n_read, 3, 0,
                                  "近5轮零新坐标", no_th=True))
            # S3 同路径 Read
            rp = {}
            for fps in win_turns:
                for name, inp in _tools(fps):
                    if name == "Read":
                        p = str(inp.get("file_path") or "")
                        if p:
                            rp[p] = rp.get(p, 0) + 1
            for p, c in sorted(rp.items(), key=lambda kv: -kv[1]):
                if c >= 3:
                    hits.append(_fine("fine[S3]", "BLOCK" if c >= 5 else "WARN",
                                      c, 3, 5, "同路径重读 %s×%d" % (p, c)))
                    break

    if any(h["level"] == "BLOCK" for h in hits):
        status = "BLOCK"
    elif any(h["level"] == "WARN" for h in hits):
        status = "WARN"
    else:
        status = "OK"
    return {"status": status, "hits": hits, "tokens": tokens,
            "last_ts": last_ts, "n_lines": n_lines,
            "fine_notes": fine_notes}


def format_report(report):
    """digest → ≤10 行文本。首行状态+信号名，命中各一行证据，末行处置建议。"""
    hits = report["hits"]
    names = ",".join(h["name"] for h in hits) if hits else "-"
    lines = ["%s %s" % (report["status"], names)]
    for h in hits:
        if h.get("no_th"):
            ev = h["detail"]
        elif h["name"] == "budget":
            ev = "%s (WARN>=80%%/BLOCK>=100%%)" % h["detail"]
        elif h["name"] == "stall":
            ev = "%s (WARN>=%ds/BLOCK>=%ds)" % (h["detail"], h["warn"], h["block"])
        else:
            ev = "%s (WARN>=%d/BLOCK>=%d)" % (h["detail"], h["warn"], h["block"])
        lines.append("%s: %s" % (h["name"], ev))
    for h in report.get("fine_notes", ()):
        lines.append("%s: %s" % (h["name"], h["detail"]))
    status = report["status"]
    if status == "BLOCK":
        ts = report["last_ts"].isoformat() if report["last_ts"] else "unknown"
        lines.append("处置: 建议 TaskStop 后分析重派；checkpoint 建议取最近时间戳 %s" % ts)
    elif status == "WARN":
        lines.append("处置: 加细探针继续观察")
    else:
        lines.append("处置: 无需处置")
    return lines[:10]


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(
        prog="probe.py",
        description="看守探针 v0：只读解析子智能体 transcript jsonl，输出 ≤10 行 digest。"
                    "退出码 0=OK 1=WARN 2=BLOCK 3=输入错误。",
        usage="python tools/probe.py <transcript.jsonl> [--budget N] [--window N]"
              " [--fine coder|scout] [--expect STR] [--expect-file PATH]")
    parser.add_argument("transcript", help="子智能体 transcript jsonl 路径（只读）")
    parser.add_argument(
        "--budget", type=float, default=None, metavar="N",
        help="输出 token 预算（口径=各行 message.usage.output_tokens 之和；"
             "达到 80%% 出 WARN、100%% 出 BLOCK；不传则不检测预算）")
    parser.add_argument(
        "--window", type=int, default=DEFAULT_WINDOW, metavar="N",
        help="检测滑窗条数：只在最近 N 条事件上判模式（默认 %d，"
             "依据 watchdog.md §2 最近事件窗口 20 条；停滞/预算按全文件统计）"
             % DEFAULT_WINDOW)
    parser.add_argument(
        "--fine", choices=("coder", "scout"), default=None, metavar="MODE",
        help="细探针类别：coder=C1/C2/C3 改动与交付判据，"
             "scout=S1/S2/S3 查询与读文件判据；不传则不启用细探针")
    parser.add_argument(
        "--expect", default=None, metavar="STR",
        help="coder 细探针 C2：验收命令应包含的子串（Bash/shell 类工具）")
    parser.add_argument(
        "--expect-file", default=None, metavar="PATH",
        help="coder 细探针 C3：交付物路径（曾被 Write/Edit 触及或已存在为正常）")
    args = parser.parse_args(argv)

    if args.budget is not None and args.budget <= 0:
        print("probe.py: 输入错误：--budget 必须为正数", file=sys.stderr)
        return 3
    if args.window is not None and args.window <= 0:
        print("probe.py: 输入错误：--window 必须为正整数", file=sys.stderr)
        return 3

    try:
        with open(args.transcript, "r", encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as exc:
        print("probe.py: 输入错误：无法读取 %s: %s"
              % (args.transcript, exc), file=sys.stderr)
        return 3

    try:
        report = analyze_text(text, window=args.window, budget=args.budget,
                              fine=args.fine, expect=args.expect,
                              expect_file=args.expect_file)
    except ValueError as exc:
        print("probe.py: 输入错误：%s" % exc, file=sys.stderr)
        return 3

    for line in format_report(report):
        print(line)
    return {"OK": 0, "WARN": 1, "BLOCK": 2}[report["status"]]


if __name__ == "__main__":
    sys.exit(main())