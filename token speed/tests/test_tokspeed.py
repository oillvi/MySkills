# -*- coding: utf-8 -*-
"""token speed 单测：配对、回合窗口、统计口径、行格式。"""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tokspeed as ts


def ev(type_, rid, turn, ts_):
    return {"type": type_, "request_id": rid, "turn_id": turn, "ts": ts_}


def usage(inp=0, cread=0, ccreate=0, out=0):
    return {
        "input_tokens": inp,
        "cache_read_input_tokens": cread,
        "cache_creation_input_tokens": ccreate,
        "output_tokens": out,
    }


class TestCompletedInTurn(unittest.TestCase):
    def test_pairs_started_and_completed_by_request_id(self):
        events = [
            ev("model.request.started", "r1", 2, "2026-09-23T10:00:00.000Z"),
            ev("model.response.completed", "r1", 2, "2026-09-23T10:00:10.000Z"),
        ]
        self.assertEqual(ts.completed_in_turn(events), [("r1", 10.0)])

    def test_inflight_request_excluded(self):
        events = [ev("model.request.started", "r1", 2, "2026-09-23T10:00:00.000Z")]
        self.assertEqual(ts.completed_in_turn(events), [])

    def test_window_defaults_to_latest_turn(self):
        events = [
            ev("model.request.started", "r1", 1, "2026-09-23T09:00:00.000Z"),
            ev("model.response.completed", "r1", 1, "2026-09-23T09:00:09.000Z"),
            ev("model.request.started", "r2", 2, "2026-09-23T10:00:00.000Z"),
            ev("model.response.completed", "r2", 2, "2026-09-23T10:00:20.000Z"),
        ]
        self.assertEqual(ts.completed_in_turn(events), [("r2", 20.0)])

    def test_explicit_turn_id_overrides_default(self):
        events = [
            ev("model.request.started", "r1", 1, "2026-09-23T09:00:00.000Z"),
            ev("model.response.completed", "r1", 1, "2026-09-23T09:00:09.000Z"),
            ev("model.request.started", "r2", 2, "2026-09-23T10:00:00.000Z"),
            ev("model.response.completed", "r2", 2, "2026-09-23T10:00:20.000Z"),
        ]
        self.assertEqual(ts.completed_in_turn(events, turn_id=1), [("r1", 9.0)])

    def test_current_turn_chronological_not_lexical(self):
        # turn_id 是 UUID：字典序最大的不一定是当前回合，按时间最后开始的算
        events = [
            ev("model.request.started", "r1", "zzz-turn", "2026-09-23T09:00:00.000Z"),
            ev("model.response.completed", "r1", "zzz-turn", "2026-09-23T09:00:09.000Z"),
            ev("model.request.started", "r2", "aaa-turn", "2026-09-23T10:00:00.000Z"),
            ev("model.response.completed", "r2", "aaa-turn", "2026-09-23T10:00:20.000Z"),
        ]
        self.assertEqual(ts.completed_in_turn(events), [("r2", 20.0)])

    def test_window_includes_subagent_requests_after_turn_start(self):
        # 子智能体请求（turn_id == session_id）在本回合起始之后的要计入（用户裁定 2026-09-23）
        events = [
            ev("model.request.started", "r1", "main-turn", "2026-09-23T10:00:00.000Z"),
            ev("model.response.completed", "r1", "main-turn", "2026-09-23T10:00:10.000Z"),
            ev("model.request.started", "r2", "S1", "2026-09-23T10:05:00.000Z"),
            ev("model.response.completed", "r2", "S1", "2026-09-23T10:05:04.000Z"),
        ]
        self.assertEqual(
            sorted(ts.completed_in_turn(events, session_id="S1")),
            sorted([("r1", 10.0), ("r2", 4.0)]),
        )

    def test_window_excludes_requests_started_before_turn_start(self):
        # 上一回合拖尾的请求（started 早于本回合起点）不计入
        events = [
            ev("model.request.started", "r0", "S1", "2026-09-23T09:50:00.000Z"),
            ev("model.response.completed", "r0", "S1", "2026-09-23T10:00:05.000Z"),
            ev("model.request.started", "r1", "main-turn", "2026-09-23T10:00:00.000Z"),
            ev("model.response.completed", "r1", "main-turn", "2026-09-23T10:00:10.000Z"),
        ]
        self.assertEqual(ts.completed_in_turn(events, session_id="S1"), [("r1", 10.0)])

    def test_retry_after_attempt_failed_measures_from_first_started(self):
        events = [
            ev("model.request.started", "r1", 3, "2026-09-23T10:00:00.000Z"),
            {"type": "model.request.attempt_failed", "request_id": "r1", "turn_id": 3,
             "ts": "2026-09-23T10:00:02.000Z"},
            ev("model.request.started", "r1", 3, "2026-09-23T10:00:03.000Z"),
            ev("model.response.completed", "r1", 3, "2026-09-23T10:00:13.000Z"),
        ]
        self.assertEqual(ts.completed_in_turn(events), [("r1", 13.0)])


class TestSummarize(unittest.TestCase):
    def test_missing_usage_counts_as_no_report(self):
        s = ts.summarize([("r1", 5.0)], {})
        self.assertEqual(s["n"], 1)
        self.assertEqual(s["n_no_usage"], 1)
        self.assertIsNone(s["tps"])

    def test_all_zero_usage_counts_as_no_report(self):
        s = ts.summarize([("r1", 5.0)], {"r1": usage()})
        self.assertEqual(s["n_no_usage"], 1)
        self.assertIsNone(s["tps"])

    def test_tps_is_total_output_over_total_duration(self):
        um = {"r1": usage(inp=10, out=100), "r2": usage(inp=10, out=50)}
        s = ts.summarize([("r1", 10.0), ("r2", 5.0)], um)
        self.assertAlmostEqual(s["tps"], 150 / 15.0)

    def test_tps_excludes_no_report_requests(self):
        um = {"r1": usage(inp=10, out=100)}
        s = ts.summarize([("r1", 10.0), ("r2", 8.0)], um)
        self.assertAlmostEqual(s["tps"], 10.0)
        self.assertAlmostEqual(s["duration_s"], 18.0)
        self.assertEqual(s["n_no_usage"], 1)

    def test_cache_rate_is_sum_cache_read_over_sum_input(self):
        um = {
            "r1": usage(inp=100, cread=80, out=5),
            "r2": usage(inp=100, cread=10, out=5),
        }
        s = ts.summarize([("r1", 1.0), ("r2", 1.0)], um)
        self.assertAlmostEqual(s["cache_rate"], 90 / 200)

    def test_total_m_counts_input_cache_creation_output(self):
        um = {"r1": usage(inp=1000, cread=200, ccreate=500, out=300)}
        s = ts.summarize([("r1", 1.0)], um)
        self.assertAlmostEqual(s["total_m"], (1000 + 500 + 300) / 1e6)

    def test_out_tokens_sums_output(self):
        um = {"r1": usage(inp=1, out=40), "r2": usage(inp=1, out=2)}
        s = ts.summarize([("r1", 1.0), ("r2", 1.0)], um)
        self.assertEqual(s["out_tokens"], 42)


class TestFormatLine(unittest.TestCase):
    def full_stats(self):
        return {
            "n": 5,
            "n_no_usage": 2,
            "tps": 71.2,
            "duration_s": 54.8,
            "out_tokens": 3854,
            "cache_rate": 0.964,
            "total_m": 0.062,
        }

    def test_line_full_metrics(self):
        s = self.full_stats()
        s["n_no_usage"] = 0
        self.assertEqual(
            ts.format_line(s),
            "tok/s: 5 req · 71.2 tok/s · out 3.9k · 54.8s · cache 96.4% · 0.062M · 末条回复不计",
        )

    def test_line_mixed_shows_no_report_count(self):
        self.assertEqual(
            ts.format_line(self.full_stats()),
            "tok/s: 5 req (2 无上报) · 71.2 tok/s · out 3.9k · 54.8s · cache 96.4% · 0.062M · 末条回复不计",
        )

    def test_line_no_report(self):
        s = {
            "n": 3,
            "n_no_usage": 3,
            "tps": None,
            "duration_s": 27.0,
            "out_tokens": 0,
            "cache_rate": None,
            "total_m": 0.0,
        }
        self.assertEqual(ts.format_line(s), "tok/s: 3 req · 无 token 上报 · 27.0s · 末条回复不计")

    def test_line_no_completed_requests(self):
        s = {
            "n": 0,
            "n_no_usage": 0,
            "tps": None,
            "duration_s": 0.0,
            "out_tokens": 0,
            "cache_rate": None,
            "total_m": 0.0,
        }
        self.assertEqual(ts.format_line(s), "tok/s: 本回合无已完成请求 · 末条回复不计")

    def test_line_small_out_count_not_scaled(self):
        s = self.full_stats()
        s["n_no_usage"] = 0
        s["out_tokens"] = 42
        s["cache_rate"] = None
        line = ts.format_line(s)
        self.assertIn("out 42 ·", line)
        self.assertNotIn("cache", line)

    def test_line_includes_model_counts(self):
        s = self.full_stats()
        s["n_no_usage"] = 0
        line = ts.format_line(s, models=[("mimo-v2.6-pro", 4), ("GLM-5.3-Flash", 1)])
        self.assertEqual(
            line,
            "tok/s: 5 req · 71.2 tok/s · out 3.9k · 54.8s · cache 96.4% · 0.062M · "
            "models: mimo-v2.6-pro×4, GLM-5.3-Flash×1 · 末条回复不计",
        )

    def test_line_no_report_with_models(self):
        s = {
            "n": 3,
            "n_no_usage": 3,
            "tps": None,
            "duration_s": 27.0,
            "out_tokens": 0,
            "cache_rate": None,
            "total_m": 0.0,
        }
        line = ts.format_line(s, models=[("auto", 3)])
        self.assertEqual(
            line, "tok/s: 3 req · 无 token 上报 · 27.0s · models: auto×3 · 末条回复不计"
        )


class TestModels(unittest.TestCase):
    def test_short_model_label_strips_provider_prefix(self):
        self.assertEqual(
            ts.short_model("qoder-custom-21fa3498-31a7-4c52-82a7-04c06fbaaee7/mimo-v2.6-pro"),
            "mimo-v2.6-pro",
        )
        self.assertEqual(ts.short_model("GLM-5.3-Flash"), "GLM-5.3-Flash")

    def test_model_counts_from_started_events(self):
        e1 = ev("model.request.started", "r1", 1, "2026-09-23T09:00:00.000Z")
        e1["data"] = {"model": "provA/m1"}
        e2 = ev("model.request.started", "r2", 1, "2026-09-23T09:00:01.000Z")
        e2["data"] = {"model": "m2"}
        counts = ts.model_counts([e1, e2], ["r1", "r2", "r1"])
        self.assertEqual(counts, [("m1", 2), ("m2", 1)])


class TestLoaders(unittest.TestCase):
    def test_load_events_parses_jsonl(self):
        raw = json.dumps(ev("model.request.started", "r1", 2, "2026-09-23T10:00:00.000Z"))
        events = ts.load_events_lines([raw, "not json", ""])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["request_id"], "r1")

    def test_load_usages_extracts_message_usage(self):
        row = {
            "type": "assistant",
            "message": {
                "model": "m1",
                "usage": usage(inp=10, out=20),
                "request_id": "r1",
            },
        }
        um = ts.load_usage_lines([json.dumps(row), "bad line"])
        self.assertEqual(um["r1"]["output_tokens"], 20)

    def test_load_usages_uses_top_level_request_id_fallback(self):
        row = {
            "request_id": "r2",
            "message": {"usage": usage(inp=1, out=2)},
        }
        um = ts.load_usage_lines([json.dumps(row)])
        self.assertIn("r2", um)

    def test_load_usage_reads_request_id_inside_usage(self):
        # 真实 jsonl 形状：request_id 在 message.usage 里面（2026-09-23 实测）
        row = {
            "type": "assistant",
            "message": {
                "model": "m1",
                "usage": {"request_id": "r9", "input_tokens": 5, "output_tokens": 20},
            },
        }
        um = ts.load_usage_lines([json.dumps(row)])
        self.assertEqual(um["r9"]["output_tokens"], 20)


class TestLatestSegment(unittest.TestCase):
    def test_latest_segment_picks_newest_mtime(self):
        with tempfile.TemporaryDirectory() as root:
            p1 = os.path.join(root, "projA", "s1", "segments", "a.jsonl")
            p2 = os.path.join(root, "projB", "s2", "segments", "b.jsonl")
            for p in (p1, p2):
                os.makedirs(os.path.dirname(p))
                with open(p, "w", encoding="utf-8") as f:
                    f.write("{}\n")
            os.utime(p1, (1000, 1000))
            os.utime(p2, (2000, 2000))
            self.assertEqual(ts.latest_segment(root), p2)

    def test_latest_segment_prefers_anchor_command_match(self):
        # 多会话并发时选「正在跑 tokspeed.py」的那个 segment，不看 mtime 谁新
        with tempfile.TemporaryDirectory() as root:
            pa = os.path.join(root, "projA", "s1", "segments", "a.jsonl")
            pb = os.path.join(root, "projB", "s2", "segments", "b.jsonl")
            for p in (pa, pb):
                os.makedirs(os.path.dirname(p))
            with open(pa, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "tool.shell.started",
                                    "ts": "2026-09-23T10:00:10.000Z",
                                    "data": {"command": "python tokspeed.py"}}) + "\n")
            with open(pb, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "tool.shell.started",
                                    "ts": "2026-09-23T10:00:09.000Z",
                                    "data": {"command": "git status"}}) + "\n")
            now = time.time()
            os.utime(pa, (now - 1, now - 1))
            os.utime(pb, (now, now))
            self.assertEqual(ts.latest_segment(root), pa)

    def test_latest_segment_anchor_ignores_stale_segments(self):
        # 旧会话（mtime 超出扫描窗）就算跑过 tokspeed 也不认
        with tempfile.TemporaryDirectory() as root:
            pa = os.path.join(root, "projA", "s1", "segments", "a.jsonl")
            pb = os.path.join(root, "projB", "s2", "segments", "b.jsonl")
            for p in (pa, pb):
                os.makedirs(os.path.dirname(p))
            with open(pa, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "tool.shell.started",
                                    "ts": "2026-09-23T10:00:10.000Z",
                                    "data": {"command": "python tokspeed.py"}}) + "\n")
            with open(pb, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "tool.shell.started",
                                    "ts": "2026-09-23T10:00:09.000Z",
                                    "data": {"command": "git status"}}) + "\n")
            now = time.time()
            os.utime(pa, (now - 7200, now - 7200))
            os.utime(pb, (now, now))
            self.assertEqual(ts.latest_segment(root), pb)


if __name__ == "__main__":
    unittest.main()
