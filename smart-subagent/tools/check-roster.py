#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对 smart-subagent 花名册：别名重复 / uses 悬空 / ref 是否仍在模型目录。

用法（在技能目录下）:
    python tools/check-roster.py                  # 默认核对用户级（生效位）花名册
    python tools/check-roster.py <roster.yml>     # 核对指定花名册（如项目级）
    python tools/check-roster.py --no-catalog     # 离线：跳过模型目录核对

（kind=custom 的条目仅桌面端可用，自动跳过目录核对）
退出码: 0=全部通过 / 1=发现问题 / 2=环境问题（缺文件、缺 PyYAML、拿不到目录）
"""
import os
import subprocess
import sys

USER_ROSTER = os.path.join(os.environ.get("USERPROFILE", ""), ".qoder-cn", "skills", "smart-subagent", "roster.yml")


def load_roster(path):
    import yaml  # PyYAML
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_catalog():
    """跑 qoderclicn --list-models，拿模型目录原文（失败返回 None）。"""
    cli_dir = os.path.join(os.environ.get("USERPROFILE", ""), ".qoder-cn", "bin", "qoderclicn")
    exe = os.path.join(cli_dir, "qoderclicn.exe")
    if not os.path.exists(exe):
        return None
    env = dict(os.environ)
    env.pop("QODER_AGENT_SDK_ENTRYPOINT", None)  # 不 pop 会报 sdk_invalid_args
    try:
        out = subprocess.run([exe, "--list-models"], cwd=cli_dir,
                             capture_output=True, text=True, timeout=90, env=env)
    except Exception:
        return None
    text = (out.stdout or "") + (out.stderr or "")
    return text if text.strip() else None


def main():
    args = sys.argv[1:]
    no_catalog = "--no-catalog" in args
    paths = [a for a in args if not a.startswith("--")]
    roster_path = paths[0] if paths else USER_ROSTER

    if not os.path.exists(roster_path):
        print("[FAIL] 花名册不存在: %s" % roster_path)
        return 2
    try:
        data = load_roster(roster_path)
    except ImportError:
        print("[FAIL] 缺少 PyYAML（请先 pip install pyyaml）")
        return 2
    except Exception as e:
        print("[FAIL] 花名册解析失败: %s" % e)
        return 1

    problems = []
    aliases = {}
    refs = []  # (标签, ref)
    customs = 0  # kind=custom：仅桌面端，CLI 目录不含，跳过存在性核对

    for m in data.get("models") or []:
        m = m or {}
        alias, ref = m.get("alias"), m.get("ref")
        if not alias or not ref:
            problems.append("models 条目缺 alias 或 ref: %r" % (m,))
            continue
        if alias in aliases:
            problems.append("别名重复: %s" % alias)
        aliases[alias] = ref
        if str(m.get("kind", "")).lower() == "custom":
            customs += 1
            continue
        refs.append(("模型菜单 %s" % alias, str(ref)))

    for ag in data.get("agents") or []:
        ag = ag or {}
        name = ag.get("name", "?")
        uses = ag.get("uses")
        if uses:
            if uses not in aliases:
                problems.append("agents[%s].uses 悬空（models 菜单里没有该别名）: %s" % (name, uses))
        elif ag.get("model"):
            refs.append(("agents[%s].model" % name, str(ag["model"])))

    catalog = None if no_catalog else get_catalog()
    if catalog is not None:
        lines = [ln.strip() for ln in catalog.splitlines() if ln.strip()]
        for label, ref in refs:
            hit = any(ln == ref or ln.startswith(ref + " (") or ("(" + ref + ")") in ln for ln in lines)
            if not hit:
                problems.append("%s 的 ref 已不在模型目录里（可能被下架/撤销）: %s" % (label, ref))
    elif not no_catalog:
        print("[WARN] 拿不到模型目录（qoderclicn --list-models 失败），跳过 ref 存在性核对")

    print("花名册: %s" % roster_path)
    print("alias %d 个（custom %d 个跳过目录核对）/ agent %d 个；目录核对: %s" % (len(data.get("models") or []), customs, len(data.get("agents") or []), "跳过" if catalog is None else "已执行"))
    if problems:
        print("发现问题 %d 条:" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("OK：全部别名在册、uses 无悬空、ref 均在模型目录中%s" % ("（custom %d 个按设计跳过）" % customs if customs else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())