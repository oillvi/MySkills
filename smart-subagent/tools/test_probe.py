#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe.py 单测：合成伪 jsonl 喂 analyze_text 检测函数（标准库 unittest）。"""
import json
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe import analyze_text, format_report  # noqa: E402

NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


def ts(offset_s=0):
    """以 NOW 为基准的 ISO 时间戳（默认紧跟“现在”，避开停滞信号）。"""
    from datetime import timedelta
    return (NOW + timedelta(seconds=offset_s)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def line(kind, content, t):
    return json.dumps({"type": kind, "timestamp": t,
                       "message": {"role": kind, "content": content}},
                      ensure_ascii=False)


def a_tool(name, inp, t=None, usage=None):
    d = {"type": "assistant", "timestamp": t or ts(),
         "message": {"content": [{"type": "tool_use", "name": name,
                                  "input": inp}]}}
    if usage:
        d["message"]["usage"] = usage
    return json.dumps(d, ensure_ascii=False)


def a_text(text, t=None):
    return line("assistant", [{"type": "text", "text": text}], t or ts())


def u_result(err=False, text="ok", t=None):
    block = {"type": "tool_result", "tool_use_id": "x", "content": text}
    if err:
        block["is_error"] = True
    return line("user", [block], t or ts())


def u_text(text, t=None):
    return line("user", [{"type": "text", "text": text}], t or ts())


def hit_names(report):
    return [h["name"] for h in report["hits"]]


def get_hit(report, name):
    return next((h for h in report["hits"] if h["name"] == name), None)


def wline(i, path="a.py"):
    """内容各异的 Write 轮，避开 repeat/fuzzy 干扰。"""
    bodies = ["install dependencies then run suite",
              "edit module function body text",
              "update configuration yaml block",
              "append changelog entry line",
              "refactor loop into helper call"]
    return a_tool("Write", {"file_path": path, "content": bodies[i % 5]})


def turns(*tool_lines):
    """每个工具行后补一条 ok 结果，保证各自成逻辑轮。"""
    out = []
    for tl in tool_lines:
        out.append(tl)
        out.append(u_result())
    return "\n".join(out)


class FineProbeTest(unittest.TestCase):
    """细探针 --fine coder|scout 判据与信息行归属。"""

    def test_c1_thresholds(self):
        """C1 同路径写 3 次=WARN、5 次=BLOCK、2 次不命中。"""
        r3 = analyze_text(turns(*[wline(i) for i in range(3)]), now=NOW,
                          fine="coder")
        self.assertEqual(r3["status"], "WARN")
        self.assertEqual(get_hit(r3, "fine[C1]")["level"], "WARN")

        r5 = analyze_text(turns(*[wline(i) for i in range(5)]), now=NOW,
                          fine="coder")
        self.assertEqual(r5["status"], "BLOCK")
        self.assertEqual(get_hit(r5, "fine[C1]")["level"], "BLOCK")

        r2 = analyze_text(turns(wline(0), wline(1)), now=NOW, fine="coder")
        self.assertNotIn("fine[C1]", hit_names(r2))
        self.assertEqual(r2["status"], "OK")

    def test_c2_zero_expect_warn(self):
        """C2 给了 expect 且 0 命中 -> WARN 行。"""
        text = turns(a_tool("Bash", {"command": "ls -la"}))
        r = analyze_text(text, now=NOW, fine="coder", expect="pytest")
        self.assertEqual(r["status"], "WARN")
        h = get_hit(r, "fine[C2]")
        self.assertIsNotNone(h)
        self.assertEqual(h["level"], "WARN")

    def test_c2_hit_not_escalate(self):
        """C2 给了 expect 且命中 1 次 -> 不抬升，且不进 hits。"""
        text = turns(a_tool("Bash", {"command": "python -m pytest -q"}))
        r = analyze_text(text, now=NOW, fine="coder", expect="pytest")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["hits"], [])
        self.assertNotIn("fine[C2]", hit_names(r))
        self.assertTrue(format_report(r)[0].startswith("OK"))

    def test_c2_without_expect_no_line(self):
        """C2 没给 expect -> 不出该行（hits 与 digest 均无 fine[C2]）。"""
        text = turns(a_tool("Bash", {"command": "python -m pytest -q"}))
        r = analyze_text(text, now=NOW, fine="coder")
        self.assertNotIn("fine[C2]", hit_names(r))
        self.assertNotIn("fine[C2]", "\n".join(format_report(r)))

    def test_c3_missing_warn(self):
        """C3 未触及且路径不存在 -> WARN。"""
        import uuid
        missing = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "_probe_missing_%s.md" % uuid.uuid4().hex)
        self.assertFalse(os.path.exists(missing))
        text = turns(a_tool("Bash", {"command": "ls"}))
        r = analyze_text(text, now=NOW, fine="coder", expect_file=missing)
        self.assertEqual(r["status"], "WARN")
        h = get_hit(r, "fine[C3]")
        self.assertIsNotNone(h)
        self.assertEqual(h["level"], "WARN")

    def test_c3_touched_ok(self):
        """C3 Write 曾触及该路径（文件可不存在）-> 不抬升。"""
        import uuid
        target = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "_probe_touched_%s.md" % uuid.uuid4().hex)
        text = turns(wline(0, path=target))
        r = analyze_text(text, now=NOW, fine="coder", expect_file=target)
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["hits"], [])
        self.assertNotIn("fine[C3]", hit_names(r))
        self.assertFalse(os.path.exists(target))

    def test_s1_thresholds(self):
        """S1 同 pattern 3 次=WARN、5 次=BLOCK。"""
        def g(i):
            return a_tool("Grep", {"pattern": "def parse_args",
                                   "path": "area%d/sub" % i})
        r3 = analyze_text(turns(*[g(i) for i in range(3)]), now=NOW,
                          fine="scout")
        self.assertEqual(get_hit(r3, "fine[S1]")["level"], "WARN")
        self.assertIn(r3["status"], ("WARN", "BLOCK"))

        r5 = analyze_text(turns(*[g(i) for i in range(5)]), now=NOW,
                          fine="scout")
        self.assertEqual(get_hit(r5, "fine[S1]")["level"], "BLOCK")
        self.assertEqual(r5["status"], "BLOCK")

    def test_s2_old_paths_warn(self):
        """S2 近5轮 ≥3 次 Read 且全为旧路径 -> 命中。"""
        text = turns(
            wline(0, path="old.py"),
            a_tool("Read", {"file_path": "old.py", "offset": 0}),
            a_tool("Read", {"file_path": "old.py", "offset": 10}),
            a_tool("Read", {"file_path": "old.py", "offset": 20}))
        r = analyze_text(text, now=NOW, fine="scout")
        self.assertIn("fine[S2]", hit_names(r))
        self.assertEqual(get_hit(r, "fine[S2]")["level"], "WARN")

    def test_s2_new_path_no_false_positive(self):
        """S2 出现新路径 Read -> 不误报。"""
        text = turns(
            wline(0, path="old.py"),
            a_tool("Read", {"file_path": "old.py", "offset": 0}),
            a_tool("Read", {"file_path": "old.py", "offset": 10}),
            a_tool("Read", {"file_path": "brand_new.py", "offset": 20}))
        r = analyze_text(text, now=NOW, fine="scout")
        self.assertNotIn("fine[S2]", hit_names(r))

    def test_s3_thresholds(self):
        """S3 同 file_path Read 3 次=WARN、5 次=BLOCK。"""
        def rd(i):
            return a_tool("Read", {"file_path": "src/main.py",
                                   "offset": i, "limit": 40 + i})
        r3 = analyze_text(turns(*[rd(i) for i in range(3)]), now=NOW,
                          fine="scout")
        self.assertEqual(get_hit(r3, "fine[S3]")["level"], "WARN")

        r5 = analyze_text(turns(*[rd(i) for i in range(5)]), now=NOW,
                          fine="scout")
        self.assertEqual(get_hit(r5, "fine[S3]")["level"], "BLOCK")
        self.assertEqual(r5["status"], "BLOCK")

    def test_no_fine_no_fine_names(self):
        """回归：同一段样本不加 fine -> hits 里不得出现 fine[...] 名。"""
        sample = turns(*[wline(i) for i in range(5)],
                       a_tool("Bash", {"command": "ls"}))
        r = analyze_text(sample, now=NOW)
        self.assertFalse(any(n.startswith("fine[") for n in hit_names(r)))
        self.assertFalse(any(n.startswith("fine[")
                             for n in format_report(r)[0].split(",")))

    def test_info_lines_not_counted_as_anomalies(self):
        """重点回归：全部正常/未达阈值 -> status OK、hits 空、首行以 OK 开头。

        C1 仅 2 次（<3）、C2 命中、C3 已触及，正常行只允许出现在
        digest 文本里，不许进 hits[]，不许混进首行名单串。
        """
        import uuid
        deliverable = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "_probe_info_%s.md" % uuid.uuid4().hex)
        text = turns(
            wline(0, path="a.py"),
            wline(1, path="a.py"),
            a_tool("Bash", {"command": "python -m pytest -q"}),
            wline(2, path=deliverable))
        r = analyze_text(text, now=NOW, fine="coder", expect="pytest",
                         expect_file=deliverable)
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["hits"], [])
        report = format_report(r)
        self.assertTrue(report[0].startswith("OK"))
        self.assertNotIn("fine[C2]", report[0])
        self.assertNotIn("fine[C3]", report[0])
        self.assertIn("验收命令命中", "\n".join(report))
        self.assertFalse(os.path.exists(deliverable))


class ProbeTest(unittest.TestCase):
    def test_repeat_exact_block(self):
        """五模式之一：同工具同参数全等重复 3 次 -> BLOCK(repeat)。"""
        same = a_tool("Bash", {"command": "ls -la"})
        text = "\n".join([same, same, same, u_result()])
        r = analyze_text(text, now=NOW)
        self.assertEqual(r["status"], "BLOCK")
        self.assertIn("repeat", hit_names(r))

    def test_normal_no_false_positive(self):
        """正常样本不误报 -> OK，且 digest 以 OK 开头。"""
        text = "\n".join([
            a_tool("Bash", {"command": "ls"}),
            u_result(),
            a_tool("Edit", {"file_path": "a.py", "old_string": "x", "new_string": "y"}),
            u_result(),
            a_text("做完了"),
            u_text("好"),
            a_tool("Bash", {"command": "pwd"}),
            u_result(),
        ])
        r = analyze_text(text, now=NOW)
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["hits"], [])
        self.assertTrue(format_report(r)[0].startswith("OK"))

    def test_error_block(self):
        """五模式之一：连续报错不收敛 3 次 -> BLOCK(error)。"""
        text = "\n".join([u_result(err=True, text="command failed"),
                          u_result(err=True, text="command failed again"),
                          u_result(err=True, text="still failing")])
        r = analyze_text(text, now=NOW)
        self.assertEqual(r["status"], "BLOCK")
        self.assertIn("error", hit_names(r))
        self.assertNotIn("context_error", hit_names(r))

    def test_monologue_block(self):
        """五模式之一：连续独白无工具产出 3 轮 -> BLOCK(monologue)。

        独白按「逻辑轮」计：连续 assistant 行（thinking/text 分行落盘）属同一轮，
        整轮无 tool_use 才算 1 条。
        """
        text = "\n".join([a_text("我在想第一步"), u_result(),
                          a_text("再想想第二步"), u_result(),
                          a_text("继续想第三步"), u_result()])
        r = analyze_text(text, now=NOW)
        self.assertEqual(r["status"], "BLOCK")
        self.assertIn("monologue", hit_names(r))

        # 防回归：同一轮内 thinking 行 + text 行相邻 = 1 条独白，不触发
        same_turn = "\n".join([a_text("思考"), a_text("回答"), u_result()])
        r2 = analyze_text(same_turn, now=NOW)
        self.assertEqual(r2["status"], "OK")

    def test_alternating_block(self):
        """五模式之一：A-B-A-B 交替 6 轮 -> BLOCK(alternating)。"""
        a = a_tool("Bash", {"command": "git status"})
        b = a_tool("Read", {"file_path": "src/main.py"})
        text = "\n".join([a, b] * 6)
        r = analyze_text(text, now=NOW)
        self.assertEqual(r["status"], "BLOCK")
        self.assertIn("alternating", hit_names(r))

    def test_context_error_block(self):
        """五模式之一：context 错误（错误文本含 context 膨胀 / 行解析坏）-> BLOCK。"""
        text = "\n".join(
            [u_result(err=True, text="Error: context window exceeded, input too large")]
            * 3)
        r = analyze_text(text, now=NOW)
        self.assertEqual(r["status"], "BLOCK")
        self.assertIn("context_error", hit_names(r))
        self.assertNotIn("error", hit_names(r))

        bad = "\n".join(["not json {{{", "also broken <<<", "### corrupted ###"])
        r2 = analyze_text(bad, now=NOW)
        self.assertEqual(r2["status"], "BLOCK")
        self.assertIn("context_error", hit_names(r2))

    def test_fuzzy_block(self):
        """模糊重复（近似循环指纹）5 次 -> BLOCK(fuzzy)。"""
        acts = [a_tool("Bash", {"command":
                                "python tools/run_step_%d --target workspace "
                                "--mode safe --repeat 3" % i})
                for i in range(1, 6)]
        r = analyze_text("\n".join(acts), now=NOW)
        self.assertEqual(r["status"], "BLOCK")
        self.assertIn("fuzzy", hit_names(r))
        self.assertNotIn("repeat", hit_names(r))

    def test_stall(self):
        """停滞：90s WARN / 300s BLOCK；末行已收尾(last-prompt)不判停滞。"""
        from datetime import timedelta
        t_old = (NOW - timedelta(seconds=400)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        t_warn = (NOW - timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        body = [a_tool("Bash", {"command": "ls"}, t=t_old), u_result(t=t_old)]
        r = analyze_text("\n".join(body + [a_tool("Bash", {"command": "pwd"}, t=t_old)]),
                         now=NOW)
        self.assertEqual(r["status"], "BLOCK")
        self.assertIn("stall", hit_names(r))

        r2 = analyze_text("\n".join(body + [a_tool("Bash", {"command": "pwd"}, t=t_warn)]),
                          now=NOW)
        self.assertEqual(r2["status"], "WARN")
        self.assertEqual(hit_names(r2), ["stall"])

        done = json.dumps({"type": "last-prompt", "timestamp": t_old,
                           "message": {"content": []}})
        r3 = analyze_text("\n".join(body + [done]), now=NOW)
        self.assertNotIn("stall", hit_names(r3))

    def test_budget(self):
        """预算：>=100% BLOCK、>=80% WARN（口径=输出 token 之和）。"""
        line_ = a_tool("Bash", {"command": "ls"}, usage={"output_tokens": 105})
        r = analyze_text(line_, budget=100, now=NOW)
        self.assertEqual(r["status"], "BLOCK")
        self.assertIn("budget", hit_names(r))
        self.assertEqual(r["tokens"], 105)

        r2 = analyze_text(line_, budget=130, now=NOW)
        self.assertEqual(r2["status"], "WARN")
        self.assertEqual(hit_names(r2), ["budget"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
