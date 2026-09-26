# -*- coding: utf-8 -*-
"""token speed 单测：配对、回合窗口、统计口径、行格式。"""
import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

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

    def _main_and_sub(self):
        return [
            ev("model.request.started", "m1", "T", "2026-09-23T10:00:00.000Z"),
            ev("model.response.completed", "m1", "T", "2026-09-23T10:00:10.000Z"),
            ev("model.request.started", "s1", "S1", "2026-09-23T10:05:00.000Z"),
            ev("model.response.completed", "s1", "S1", "2026-09-23T10:05:05.000Z"),
        ]

    def test_role_all_is_default(self):
        self.assertEqual(
            sorted(ts.completed_in_turn(self._main_and_sub(), session_id="S1")),
            sorted([("m1", 10.0), ("s1", 5.0)]))

    def test_role_main_excludes_subagent_requests(self):
        self.assertEqual(
            ts.completed_in_turn(self._main_and_sub(), session_id="S1", role="main"),
            [("m1", 10.0)])

    def test_role_sub_returns_only_subagent_requests(self):
        self.assertEqual(
            ts.completed_in_turn(self._main_and_sub(), session_id="S1", role="sub"),
            [("s1", 5.0)])

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


def stats(n=5, n_no_usage=0, tps=71.2, duration_s=54.8, out_tokens=3854,
          cache_rate=0.964, total_m=0.062):
    return {"n": n, "n_no_usage": n_no_usage, "tps": tps, "duration_s": duration_s,
            "out_tokens": out_tokens, "cache_rate": cache_rate, "total_m": total_m}


class TestFormatLine(unittest.TestCase):
    def full_stats(self):
        return stats()

    def test_line_full_metrics(self):
        self.assertEqual(
            ts.format_line(self.full_stats()),
            "tok/s: 5 req · 71.2 tok/s · out 3.9k · 54.8s · cache 96.4% · 0.062M")

    def test_line_drops_tail_note(self):
        # 用户裁定 2026-09-26：`末条回复不计` 不再出现在尾行（口径留在文档里）
        cases = [
            ts.format_line(self.full_stats()),
            ts.format_line(stats(n=5, n_no_usage=2), models=[("m1", 5, 71.2, 2)]),
            ts.format_line(stats(n=0, tps=None, duration_s=0.0, cache_rate=None,
                                 total_m=0.0)),
            ts.format_line(stats(n=3, n_no_usage=3, tps=None, out_tokens=0,
                                 cache_rate=None, total_m=0.0)),
        ]
        for line in cases:
            self.assertNotIn("末条", line)

    def test_line_mixed_shows_no_report_count(self):
        s = stats(n=5, n_no_usage=2)
        self.assertEqual(
            ts.format_line(s),
            "tok/s: 5 req (2 无上报) · 71.2 tok/s · out 3.9k · 54.8s · cache 96.4% · 0.062M")

    def test_line_no_report(self):
        s = stats(n=3, n_no_usage=3, tps=None, duration_s=27.0, out_tokens=0,
                  cache_rate=None, total_m=0.0)
        self.assertEqual(ts.format_line(s), "tok/s: 3 req · 无 token 上报 · 27.0s")

    def test_line_no_completed_requests(self):
        s = stats(n=0, tps=None, duration_s=0.0, out_tokens=0, cache_rate=None, total_m=0.0)
        self.assertEqual(ts.format_line(s), "tok/s: 本回合无已完成请求")

    def test_line_small_out_count_not_scaled(self):
        s = stats(out_tokens=42, cache_rate=None)
        line = ts.format_line(s)
        self.assertIn("out 42 ·", line)
        self.assertNotIn("cache", line)

    def test_line_models_include_per_model_tps(self):
        line = ts.format_line(
            stats(), models=[("mimo-v2.6-pro", 4, 71.2, 0), ("GLM-5.3-Flash", 1, 130.0, 0)])
        self.assertEqual(
            line,
            "tok/s: 5 req · 71.2 tok/s · out 3.9k · 54.8s · cache 96.4% · 0.062M · "
            "models: mimo-v2.6-pro×4 71.2 tok/s, GLM-5.3-Flash×1 130.0 tok/s")

    def test_line_marks_no_report_model_while_other_has_tps(self):
        line = ts.format_line(stats(),
                              models=[("mimo-v2.6-pro", 4, 71.2, 0), ("auto", 1, None, 1)])
        self.assertIn("models: mimo-v2.6-pro×4 71.2 tok/s, auto×1 无上报", line)

    def test_line_partial_no_report_within_listed_model(self):
        line = ts.format_line(stats(n=5, n_no_usage=2),
                              models=[("mimo-v2.6-pro", 4, 71.2, 1), ("auto", 1, None, 1)])
        self.assertIn(
            "models: mimo-v2.6-pro×4 71.2 tok/s (1 无上报), auto×1 无上报", line)

    def test_line_single_main_model_is_not_repeated(self):
        # 用户裁定 2026-09-26：主段只有一个模型时不再列 models（避免重复报主模型速度）
        line = ts.format_line(stats(), models=[("mimo-v2.6-pro", 5, 71.2, 0)])
        self.assertNotIn("models:", line)

    def test_line_single_model_still_named_when_no_report(self):
        s = stats(n=3, n_no_usage=3, tps=None, out_tokens=0, cache_rate=None, total_m=0.0)
        line = ts.format_line(s, models=[("auto", 3, None, 3)])
        self.assertEqual(
            line, "tok/s: 3 req · 无 token 上报 · 54.8s · models: auto×3 无上报")


class TestMainSubSplit(unittest.TestCase):
    """用了子智能体时主一行、每个子模型各一行（用户裁定 2026-09-26，二次改为分行板书）。"""

    def main_s(self):
        return stats(n=12, tps=40.2, duration_s=210.0, out_tokens=8400,
                     cache_rate=0.913, total_m=0.32)

    def sub_flash(self):
        return stats(n=6, tps=21.5, duration_s=88.4, out_tokens=1900,
                     cache_rate=0.88, total_m=0.062)

    def sub_deep(self):
        return stats(n=2, tps=44.5, duration_s=40.0, out_tokens=1780,
                     cache_rate=0.7, total_m=0.02)

    def test_no_subagent_keeps_single_plain_line(self):
        line = ts.format_line(self.main_s(), models=[("qwen3.8-max", 12, 40.2, 0)])
        self.assertEqual(line, "tok/s: 12 req · 40.2 tok/s · out 8.4k · 210.0s · "
                               "cache 91.3% · 0.320M")
        self.assertNotIn("\n", line)
        self.assertNotIn("主", line)

    def test_one_subagent_model_adds_one_own_line(self):
        out = ts.format_line(self.main_s(), models=[("qwen3.8-max", 12, 40.2, 0)],
                             sub_models=[("mimo-v2.6-flash", self.sub_flash())])
        self.assertEqual(out.split("\n"), [
            "tok/s: 主 12 req · 40.2 tok/s · out 8.4k · 210.0s · cache 91.3% · 0.320M",
            "tok/s: 子 mimo-v2.6-flash×6 · 21.5 tok/s · out 1.9k · 88.4s · cache 88.0% · 0.062M",
        ])

    def test_each_subagent_model_gets_its_own_line(self):
        out = ts.format_line(self.main_s(),
                             sub_models=[("mimo-v2.6-flash", self.sub_flash()),
                                         ("deepseek-flash", self.sub_deep())])
        lines = out.split("\n")
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("tok/s: 主 "))
        self.assertEqual(lines[1], "tok/s: 子 mimo-v2.6-flash×6 · 21.5 tok/s · out 1.9k · "
                                   "88.4s · cache 88.0% · 0.062M")
        self.assertEqual(lines[2], "tok/s: 子 deepseek-flash×2 · 44.5 tok/s · out 1.8k · "
                                   "40.0s · cache 70.0% · 0.020M")

    def test_sub_model_speed_is_not_the_main_one(self):
        out = ts.format_line(self.main_s(), models=[("qwen3.8-max", 12, 40.2, 0)],
                             sub_models=[("mimo-v2.6-flash", self.sub_flash())])
        self.assertNotIn("qwen3.8-max", out.split("\n")[1])
        self.assertEqual(out.count("40.2 tok/s"), 1)
        self.assertEqual(out.count("21.5 tok/s"), 1)

    def test_no_blended_total_line_for_sub(self):
        # 分行之后不再给「子合计」：掺出来的速度没意义
        out = ts.format_line(self.main_s(), sub_models=[("flash", self.sub_flash()),
                                                        ("dsv41", self.sub_deep())])
        self.assertNotIn("子 8 req", out)
        self.assertNotIn("models:", out)

    def test_sub_line_without_usage_reports_duration_only(self):
        s = stats(n=3, n_no_usage=3, tps=None, duration_s=27.0, out_tokens=0,
                  cache_rate=None, total_m=0.0)
        out = ts.format_line(self.main_s(), sub_models=[("auto", s)])
        self.assertEqual(out.split("\n")[1],
                         "tok/s: 子 auto×3 · 无 token 上报 · 27.0s")

    def test_sub_line_partial_no_report(self):
        s = stats(n=6, n_no_usage=2, tps=21.5, duration_s=88.4, out_tokens=1900,
                  cache_rate=0.88, total_m=0.062)
        out = ts.format_line(stats(n=12, n_no_usage=4, tps=40.2, duration_s=210.0,
                                   out_tokens=8400, cache_rate=0.913, total_m=0.32),
                             sub_models=[("flash", s)])
        self.assertIn("主 12 req (4 无上报)", out.split("\n")[0])
        self.assertIn("子 flash×6 (2 无上报)", out.split("\n")[1])

    def test_sub_only_when_main_has_nothing(self):
        main = stats(n=0, tps=None, duration_s=0.0, out_tokens=0, cache_rate=None,
                     total_m=0.0)
        out = ts.format_line(main, sub_models=[("mimo-v2.6-flash", self.sub_flash())])
        self.assertEqual(out, "tok/s: 子 mimo-v2.6-flash×6 · 21.5 tok/s · out 1.9k · "
                              "88.4s · cache 88.0% · 0.062M")

    def test_both_empty(self):
        empty = stats(n=0, tps=None, duration_s=0.0, out_tokens=0, cache_rate=None,
                      total_m=0.0)
        self.assertEqual(ts.format_line(empty, sub_models=[("flash", empty)]),
                         "tok/s: 本回合无已完成请求")


class TestModelGroups(unittest.TestCase):
    def _started(self, rid, model, turn="T"):
        e = ev("model.request.started", rid, turn, "2026-09-23T09:00:00.000Z")
        e["data"] = {"model": model}
        return e

    def test_groups_carry_full_summary_per_model(self):
        events = [self._started("r1", "p/flash"), self._started("r2", "p/flash"),
                  self._started("r3", "dsv41")]
        um = {"r1": usage(inp=1000, cread=900, out=200),
              "r2": usage(inp=1000, cread=600, out=100),
              "r3": usage(inp=500, cread=250, out=100)}
        reqs = [("r1", 10.0), ("r2", 10.0), ("r3", 5.0)]
        groups = ts.model_groups(events, reqs, um)
        self.assertEqual([label for label, _s in groups], ["flash", "dsv41"])
        flash = dict(groups)["flash"]
        self.assertEqual(flash["n"], 2)
        self.assertAlmostEqual(flash["tps"], 15.0)          # 300 out / 20s
        self.assertAlmostEqual(flash["cache_rate"], 0.75)   # 1500 read / 2000 input
        self.assertAlmostEqual(flash["total_m"], (2000 + 300) / 1e6)

    def test_groups_unlabeled_request_is_not_dropped(self):
        events = [ev("model.request.started", "r1", "T", "2026-09-23T09:00:00.000Z")]
        groups = ts.model_groups(events, [("r1", 4.0)], {"r1": usage(out=40)})
        self.assertEqual(groups[0][0], "未标注")
        self.assertEqual(groups[0][1]["n"], 1)

    def test_model_stats_is_the_thin_view_of_groups(self):
        events = [self._started("r1", "flash"), self._started("r2", "dsv41")]
        um = {"r1": usage(out=100), "r2": usage(out=40)}
        reqs = [("r1", 10.0), ("r2", 4.0)]
        self.assertEqual(ts.model_stats(events, reqs, um),
                         [(label, s["n"], s["tps"], s["n_no_usage"])
                          for label, s in ts.model_groups(events, reqs, um)])

    def test_groups_sorted_by_count_desc_then_name(self):
        events = [self._started("r%d" % i, m) for i, m in
                  enumerate(["b", "a", "b", "a", "c"], start=1)]
        groups = ts.model_groups(events, [("r%d" % i, 1.0) for i in range(1, 6)], {})
        self.assertEqual([label for label, _s in groups], ["a", "b", "c"])




class TestModels(unittest.TestCase):
    def test_short_model_label_strips_provider_prefix(self):
        self.assertEqual(
            ts.short_model("qoder-custom-21fa3498-31a7-4c52-82a7-04c06fbaaee7/mimo-v2.6-pro"),
            "mimo-v2.6-pro",
        )
        self.assertEqual(ts.short_model("GLM-5.3-Flash"), "GLM-5.3-Flash")

    def _started(self, rid, model):
        e = ev("model.request.started", rid, 1, "2026-09-23T09:00:00.000Z")
        e["data"] = {"model": model}
        return e

    def test_model_stats_per_model_independent_tps(self):
        events = [self._started("r1", "provA/m1"), self._started("r2", "provA/m1"),
                  self._started("r3", "m2")]
        um = {"r1": usage(out=100), "r2": usage(out=100), "r3": usage(out=40)}
        rows = ts.model_stats(events, [("r1", 10.0), ("r2", 10.0), ("r3", 4.0)], um)
        self.assertEqual(rows, [("m1", 2, 10.0, 0), ("m2", 1, 10.0, 0)])

    def test_model_stats_no_usage_model_is_none_not_zero(self):
        events = [self._started("r1", "m1"), self._started("r2", "m2")]
        um = {"r1": usage(out=100)}
        rows = ts.model_stats(events, [("r1", 10.0), ("r2", 5.0)], um)
        self.assertEqual(rows, [("m1", 1, 10.0, 0), ("m2", 1, None, 1)])

    def test_model_stats_partial_no_report_within_model(self):
        events = [self._started("r1", "m1"), self._started("r2", "m1")]
        um = {"r1": usage(out=100)}
        rows = ts.model_stats(events, [("r1", 10.0), ("r2", 8.0)], um)
        self.assertEqual(rows, [("m1", 2, 10.0, 1)])

    def test_model_stats_sorted_by_count_desc_then_name(self):
        events = [self._started("r%d" % i, m) for i, m in
                  enumerate(["b", "a", "b", "a", "c"], start=1)]
        rows = ts.model_stats(events, [("r%d" % i, 1.0) for i in range(1, 6)], {})
        self.assertEqual([(r[0], r[1]) for r in rows], [("a", 2), ("b", 2), ("c", 1)])


ROSTER_SAMPLE = """\
# smart-subagent 模型花名册 · 测试样本
version: 2
models:
  # —— Qoder 系统自带 ——
  - alias: qoder-glm-5.3-flash
    ref: GLM-5.3-Flash
    kind: system
  # —— BYOK（ref 写 UUID）——
  - alias: deepseek-flash
    ref: 4e190e86-5f73-469d-8a98-f529eb0524a7
    kind: byok
  - alias: glm-5.3-flash
    ref: baab57d8-3c3b-487b-ad4b-9fdae674ffd0
    kind: byok
  - alias: mimo-v2.6-pro
    ref: mimo-v2.6-pro
    kind: custom
    note: 自定义 provider；仅桌面端
agents:
  - name: glm-scout
    uses: qoder-glm-5.3-flash         # 引用菜单别名
"""


class TestRosterNames(unittest.TestCase):
    def amap(self):
        return ts.build_alias_map(ts.parse_roster_aliases(ROSTER_SAMPLE))

    def test_parse_roster_pairs_from_models_section(self):
        pairs = ts.parse_roster_aliases(ROSTER_SAMPLE)
        self.assertEqual(len(pairs), 4)
        self.assertIn(("deepseek-flash", "4e190e86-5f73-469d-8a98-f529eb0524a7"), pairs)
        self.assertIn(("mimo-v2.6-pro", "mimo-v2.6-pro"), pairs)

    def test_roster_alias_maps_uuid_to_alias(self):
        amap = self.amap()
        self.assertEqual(
            ts.roster_alias("4e190e86-5f73-469d-8a98-f529eb0524a7", amap), "deepseek-flash")
        self.assertEqual(
            ts.roster_alias("qoder-custom-x/baab57d8-3c3b-487b-ad4b-9fdae674ffd0", amap),
            "glm-5.3-flash")

    def test_roster_alias_keeps_human_names_and_unknown_uuids(self):
        amap = self.amap()
        self.assertEqual(ts.roster_alias("GLM-5.3-Flash", amap), "GLM-5.3-Flash")
        self.assertEqual(ts.roster_alias("mimo-v2.6-pro", amap), "mimo-v2.6-pro")
        self.assertEqual(
            ts.roster_alias("deadbeef-0000-0000-0000-000000000000", amap),
            "deadbeef-0000-0000-0000-000000000000")
        self.assertEqual(
            ts.roster_alias("4e190e86-5f73-469d-8a98-f529eb0524a7", {}),
            "4e190e86-5f73-469d-8a98-f529eb0524a7")

    def test_model_stats_uses_roster_alias(self):
        e = ev("model.request.started", "r1", 1, "2026-09-23T09:00:00.000Z")
        e["data"] = {"model": "4e190e86-5f73-469d-8a98-f529eb0524a7"}
        rows = ts.model_stats([e], [("r1", 5.0)], {"r1": usage(out=50)}, alias_map=self.amap())
        self.assertEqual(rows, [("deepseek-flash", 1, 10.0, 0)])

    def test_load_roster_map_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(ts.load_roster_map(os.path.join(root, "nope.yml")), {})

    def test_load_roster_map_reads_file(self):
        with tempfile.TemporaryDirectory() as root:
            p = os.path.join(root, "roster.yml")
            with open(p, "w", encoding="utf-8") as f:
                f.write(ROSTER_SAMPLE)
            amap = ts.load_roster_map(p)
            self.assertEqual(amap.get("4e190e86-5f73-469d-8a98-f529eb0524a7"), "deepseek-flash")


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


class TestSubagentUsage(unittest.TestCase):
    def _row(self, rid, out):
        return json.dumps({"type": "assistant",
                           "message": {"usage": {"request_id": rid, "output_tokens": out}}})

    def test_load_subagent_usages_reads_transcripts(self):
        with tempfile.TemporaryDirectory() as root:
            d = os.path.join(root, "subagents")
            os.makedirs(d)
            with open(os.path.join(d, "agent-ax-1.jsonl"), "w", encoding="utf-8") as f:
                f.write(self._row("r1", 50) + "\n")
            with open(os.path.join(d, "agent-ay-2.jsonl"), "w", encoding="utf-8") as f:
                f.write(self._row("r2", 9) + "\n")
            got = ts.load_subagent_usages(d, wanted={"r1"})
            self.assertIn("r1", got)
            self.assertNotIn("r2", got)

    def test_load_subagent_usages_missing_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(ts.load_subagent_usages(os.path.join(root, "nope")), {})

    def test_merge_missing_keeps_base_priority(self):
        base = {"r1": {"output_tokens": 1}}
        merged = ts.merge_missing(base, {"r1": {"output_tokens": 2}, "r2": {"output_tokens": 3}})
        self.assertEqual(merged["r1"]["output_tokens"], 1)
        self.assertEqual(merged["r2"]["output_tokens"], 3)


class TestMainEndToEnd(unittest.TestCase):
    def _home(self, home, proj="P", sid="S1", sub=True, sub_out=20):
        seg_dir = os.path.join(home, "logs", "sessions", proj, sid, "segments")
        os.makedirs(seg_dir)
        events = [
            ev("model.request.started", "m1", "T-main", "2026-09-23T10:00:00.000Z"),
            ev("model.response.completed", "m1", "T-main", "2026-09-23T10:00:10.000Z"),
        ]
        if sub:
            events += [
                ev("model.request.started", "s1", sid, "2026-09-23T10:05:00.000Z"),
                ev("model.response.completed", "s1", sid, "2026-09-23T10:05:05.000Z"),
            ]
        for e in events:
            e["data"] = {"model": "sub-model" if e["turn_id"] == sid else "main-model"}
        with open(os.path.join(seg_dir, "run.jsonl"), "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
        pdir = os.path.join(home, "projects", proj)
        os.makedirs(os.path.join(pdir, sid, "subagents"))
        with open(os.path.join(pdir, sid + ".jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "assistant",
                                "message": {"usage": {"request_id": "m1",
                                                      "input_tokens": 1000,
                                                      "output_tokens": 100}}}) + "\n")
        if sub:
            with open(os.path.join(pdir, sid, "subagents", "agent-asub-1.jsonl"),
                      "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "assistant",
                                    "message": {"usage": {"request_id": "s1",
                                                          "input_tokens": 500,
                                                          "output_tokens": sub_out}}}) + "\n")

    def _run(self, home):
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"QODER_CN_HOME": home}), \
                contextlib.redirect_stdout(buf):
            rc = ts.main()
        return rc, buf.getvalue().rstrip("\n")

    def test_main_reports_main_and_sub_on_separate_lines(self):
        with tempfile.TemporaryDirectory() as home:
            self._home(home)
            rc, out = self._run(home)
            self.assertEqual(rc, 0)
            # 主：100 out / 10s = 10.0；子：20 out / 5s = 4.0 —— 各一行，互不掺
            self.assertEqual(out.split("\n"), [
                "tok/s: 主 1 req · 10.0 tok/s · out 100 · 10.0s · cache 0.0% · 0.001M",
                "tok/s: 子 sub-model×1 · 4.0 tok/s · out 20 · 5.0s · cache 0.0% · 0.001M",
            ])
            self.assertNotIn("main-model", out)
            self.assertNotIn("末条", out)

    def test_main_without_subagent_has_no_role_labels(self):
        with tempfile.TemporaryDirectory() as home:
            self._home(home, sub=False)
            _rc, line = self._run(home)
            self.assertEqual(
                line,
                "tok/s: 1 req · 10.0 tok/s · out 100 · 10.0s · cache 0.0% · 0.001M")

    def test_subagent_usage_comes_from_transcript_not_parent(self):
        # 父会话 jsonl 里没有 s1 的 usage：删掉转录则子行应报「无 token 上报」
        with tempfile.TemporaryDirectory() as home:
            self._home(home)
            p = os.path.join(home, "projects", "P", "S1", "subagents", "agent-asub-1.jsonl")
            os.remove(p)
            _rc, out = self._run(home)
            self.assertEqual(out.split("\n")[1],
                             "tok/s: 子 sub-model×1 · 无 token 上报 · 5.0s")
            self.assertIn("主 1 req · 10.0 tok/s", out.split("\n")[0])



if __name__ == "__main__":
    unittest.main()
