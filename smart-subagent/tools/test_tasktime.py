# -*- coding: utf-8 -*-
"""tasktime.py 的单元测试（标准库 unittest，全部使用临时假会话目录）。"""

import contextlib
import io
import json
import os
import tempfile
import unittest

import tasktime


def run_tasktime(*argv):
    """调用 tasktime.main 并返回捕获到的 stdout 文本。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = tasktime.main(list(argv))
    return code, buf.getvalue()


class TasktimeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name
        self.sid = os.path.join(self.root, "sess-1")
        self.sub = os.path.join(self.sid, "subagents")
        os.makedirs(self.sub)

    def write_task(self, filename, **fields):
        path = os.path.join(self.sub, filename)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(fields, fh, ensure_ascii=False)
        return path

    def write_transcript(self, filename, *timestamps):
        path = os.path.join(self.sub, filename)
        with open(path, "w", encoding="utf-8") as fh:
            for i, ts in enumerate(timestamps):
                fh.write(json.dumps({"timestamp": ts, "i": i}) + "\n")
        return path

    # 1) completedAt - createdAt 的墙钟、来源 task-json、按 createdAt 升序
    def test_wall_clock_from_completed_at_and_order_by_created(self):
        self.write_task(
            "task-later.json",
            invocationName="adb-d2",
            agentType="mimo-worker",
            status="completed",
            description="later task",
            createdAt=1790437301113,
            updatedAt=1790438261603,
            completedAt=1790438261602,
        )
        self.write_task(
            "task-early.json",
            invocationName="adb-d1",
            agentType="mimo-worker",
            status="completed",
            description="抽取 ADB 主站 leaderboard 数据",
            createdAt=1790437261412,
            updatedAt=1790437890143,
            completedAt=1790437890142,
        )
        code, out = run_tasktime("--session-dir", self.sid)
        self.assertEqual(code, 0)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 3)
        self.assertEqual(
            lines[0],
            "adb-d1  completed  628.7s  task-json  抽取 ADB 主站 leaderboard 数据",
        )
        self.assertEqual(lines[1], "adb-d2  completed  960.5s  task-json  later task")
        self.assertIn("total  2 个", lines[2])

    # 2) completedAt 缺失但 updatedAt 在 → 用 updatedAt
    def test_falls_back_to_updated_at_when_completed_at_missing(self):
        self.write_task(
            "task-a.json",
            invocationName="adb-run",
            agentType="mimo-worker",
            status="running",
            description="updated only",
            createdAt=1790437261412,
            updatedAt=1790437500000,
        )
        code, out = run_tasktime("--session-dir", self.sid)
        self.assertEqual(code, 0)
        self.assertIn("adb-run  running  238.6s  task-json  updated only", out)

    # 3) 无任何时间戳、transcript 有效 → transcript 首末 timestamp 差
    def test_uses_transcript_when_task_json_has_no_timestamps(self):
        self.write_task(
            "task-t.json",
            invocationName="adb-t",
            agentType="mimo-worker",
            status="completed",
            description="from transcript",
            transcriptPath=os.path.join(self.sub, "agent-t.jsonl"),
        )
        self.write_transcript(
            "agent-t.jsonl",
            "2026-09-26T15:41:01.472Z",
            "2026-09-26T15:41:02.472Z",
            "2026-09-26T15:42:09.472Z",
            "2026-09-26T15:51:30.172Z",
        )
        code, out = run_tasktime("--session-dir", self.sid)
        self.assertEqual(code, 0)
        self.assertIn("adb-t  completed  628.7s  transcript  from transcript", out)

    # 4) 时间戳与 transcript 都拿不到 → ?s + missing，不抛异常
    def test_missing_everything_yields_question_mark(self):
        self.write_task(
            "task-m.json",
            invocationName="adb-m",
            agentType="mimo-worker",
            status="failed",
            description="nothing available",
            transcriptPath=os.path.join(self.sub, "does-not-exist.jsonl"),
        )
        code, out = run_tasktime("--session-dir", self.sid)
        self.assertEqual(code, 0)
        self.assertIn("adb-m  failed  ?s  missing  nothing available", out)
        self.assertIn("total  1 个 · 完成 0 个 · sum 0.0s · span ?", out)

    # 5) 合计行 4 个数全断言（两个错峰任务）
    def test_total_line_all_four_numbers(self):
        self.write_task(
            "task-one.json",
            invocationName="t-one",
            agentType="mimo-worker",
            status="completed",
            description="first",
            createdAt=1790437261412,
            updatedAt=1790437500000,
            completedAt=1790437500000,
        )
        self.write_task(
            "task-two.json",
            invocationName="t-two",
            agentType="mimo-worker",
            status="completed",
            description="second",
            createdAt=1790437300000,
            updatedAt=1790437700000,
            completedAt=1790437700000,
        )
        code, out = run_tasktime("--session-dir", self.sid)
        self.assertEqual(code, 0)
        total = [ln for ln in out.splitlines() if ln.startswith("total")][0]
        # 238.588s + 400.0s = 638.588s → 638.6s
        self.assertEqual(
            total, "total  2 个 · 完成 2 个 · sum 638.6s · span 438.6s"
        )

    # 6) 目录里没有 task-*.json
    def test_no_tasks_prints_notice_and_exits_zero(self):
        code, out = run_tasktime("--session-dir", self.sid)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "no subagent tasks found")

    # 附加：目录不存在 → 3，错误走 stderr
    def test_missing_directory_returns_3(self):
        err = io.StringIO()
        missing = os.path.join(self.root, "nope")
        with contextlib.redirect_stderr(err):
            code = tasktime.main(["--session-dir", missing])
        self.assertEqual(code, 3)
        self.assertTrue(err.getvalue().strip())


if __name__ == "__main__":
    unittest.main(verbosity=2)
