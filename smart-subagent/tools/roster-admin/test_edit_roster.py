#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""edit_roster 外科式编辑的单测：不过测试 = 不能动真花名册。

跑法（可复现）:
    python tools/roster-admin/test_edit_roster.py
退出码: 0=全过 / 1=有失败
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import server  # noqa: E402

ROSTER = Path(server.ROSTER_PATH)


def load():
    import yaml
    text = ROSTER.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return text, data


def test_noop():
    """原样数据进、原样文本出：一个字节都不能变。"""
    text, data = load()
    out = server.edit_roster(text, data["models"], data["agents"],
                             data.get("routing") or {}, data.get("on_out_of_roster") or "report")
    assert out == text, "no-op 改写了文本（差 %d 字节）" % abs(len(out) - len(text))
    print("PASS test_noop")


def test_mutations():
    """改 note / 增 / 删 / 改路由 / 改 on_out_of_roster，注释与未动条目原样保留。"""
    import yaml
    text, data = load()
    models = [dict(m) for m in data["models"]]
    models[0]["note"] = "测试备注-改"
    dropped = models[-1]["alias"]
    models = models[:-1]
    models.append({"alias": "test-only-model", "ref": "qoder-custom-test/test-only-model",
                   "kind": "custom", "note": "测试条目"})
    agents = [dict(a) for a in data["agents"]]
    routing = dict(data.get("routing") or {})
    routing["tester"] = agents[0]["name"]

    out = server.edit_roster(text, models, agents, routing, "inline")
    new = yaml.safe_load(out)

    assert new["models"][0]["note"] == "测试备注-改", "note 改写失败"
    assert dropped not in [m["alias"] for m in new["models"]], "删除失败"
    assert "test-only-model" in [m["alias"] for m in new["models"]], "新增失败"
    assert new["routing"].get("tester") == agents[0]["name"], "routing 新增失败"
    assert new["on_out_of_roster"] == "inline", "on_out_of_roster 改写失败"
    assert out.splitlines()[0] == text.splitlines()[0], "文件头注释丢了"
    assert "# —— Qoder 系统自带" in out, "分区注释丢了"
    kept = [m for m in new["models"] if m["alias"] == models[1]["alias"]][0]
    assert kept == data["models"][1], "未动条目被改形"
    for orig in data["models"]:                     # 全量对账：除改 note 的首条与被删条目
        if orig["alias"] in (dropped, models[0]["alias"]):
            continue
        got = [m for m in new["models"] if m["alias"] == orig["alias"]]
        assert got == [orig], ("条目被改形", orig, got)
    assert new["agents"] == data["agents"], "agents 段被动过"
    print("PASS test_mutations")
    return out


def test_field_removal():
    """payload 里没有的字段 = 删掉（还原场景）；注释仍要保住。"""
    import yaml
    text, data = load()
    models = [dict(m) for m in data["models"]]
    models[0] = dict(models[0], note="临时备注")
    out1 = server.edit_roster(text, models, data["agents"],
                              data.get("routing") or {}, data.get("on_out_of_roster") or "report")
    assert "临时备注" in out1, "加 note 失败"
    models[0].pop("note")                     # 还原：payload 不带 note
    out2 = server.edit_roster(out1, models, data["agents"],
                              data.get("routing") or {}, data.get("on_out_of_roster") or "report")
    assert "临时备注" not in out2, "删 note 失败"
    assert out2 == text, "还原后文本与原文不一致"
    print("PASS test_field_removal")


if __name__ == "__main__":
    failed = 0
    for fn in (test_noop, test_mutations, test_field_removal):
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print("FAIL %s: %s" % (fn.__name__, e))
    print("== %d failed ==" % failed)
    sys.exit(1 if failed else 0)
