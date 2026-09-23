#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对 smart-subagent 花名册：别名重复 / uses 悬空 / ref 是否仍在模型目录。

用法（在技能目录下）:
    python tools/check-roster.py                  # 默认核对用户级（生效位）花名册
    python tools/check-roster.py <roster.yml>     # 核对指定花名册（如项目级）
    python tools/check-roster.py --no-catalog     # 离线：跳过模型目录核对
    python tools/check-roster.py --menu           # 菜单对账：Qoder 侧 vs 花名册两向差异
                                                  #   （只报告不判失败，退出码恒 0；可与 --no-catalog 共存）

（kind=custom 的条目仅桌面端可用，自动跳过目录核对）
退出码（无 --menu 时）: 0=全部通过 / 1=发现问题 / 2=环境问题（缺文件、缺 PyYAML、拿不到目录）
"""
import json
import os
import subprocess
import sys

USER_ROSTER = os.path.join(os.environ.get("USERPROFILE", ""), ".qoder-cn", "skills", "smart-subagent", "roster.yml")
SETTINGS_JSON = os.path.join(os.environ.get("USERPROFILE", ""), ".qoder-cn", "settings.json")  # 只读：本脚本绝不写它


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


def get_settings_models():
    """读 ~/.qoder-cn/settings.json 的 providers[].models[].model 模型名（纯读，绝不写）。

    返回 (模型名集合, None) 或 (None, WARN 说明)。
    """
    if not os.path.exists(SETTINGS_JSON):
        return None, "settings.json 不存在，自定义 provider 项跳过: %s" % SETTINGS_JSON
    try:
        with open(SETTINGS_JSON, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        return None, "settings.json 解析失败，自定义 provider 项跳过: %s" % e
    providers = cfg.get("providers")
    if not isinstance(providers, dict) or not providers:
        return None, "settings.json 里找不到 providers，自定义 provider 项跳过: %s" % SETTINGS_JSON
    names = set()
    for pv in providers.values():
        for mm in (pv or {}).get("models") or []:
            n = (mm or {}).get("model")
            if n:
                names.add(str(n))  # 多个 provider 下同名模型靠 set 去重计一条
    return names, None


def collect_catalog_names(catalog):
    """把 --list-models 原文压成模型名集合（跳过 MODEL 表头；兼容 `名 (备注)` / `显示 (名)` 两式）。"""
    names = set()
    for ln in catalog.splitlines():
        ln = ln.strip()
        if not ln or ln == "MODEL":
            continue
        if " (" in ln and ln.endswith(")"):
            head, tail = ln.split(" (", 1)
            names.add(head.strip())
            names.add(tail[:-1].strip())
        else:
            names.add(ln)
    return names


def roster_model_names(data):
    """花名册 models[].ref → 模型名集合；custom 全路径 `qoder-custom-<key>/<名>` 取最后一个 / 后的段。"""
    names = set()
    for m in data.get("models") or []:
        m = m or {}
        ref = m.get("ref")
        if ref:
            names.add(str(ref).rsplit("/", 1)[-1])
    return names


def menu_report(roster_path, no_catalog=False):
    """--menu：Qoder 侧（CLI 目录 + settings 自定义 provider）与花名册两向对账；只报告，退出码恒 0。"""
    print("== 菜单对账（--menu，只读） ==")
    print("数据源: qoderclicn --list-models（系统/BYOK） + %s 的 providers[].models[]（纯读）" % SETTINGS_JSON)

    qoder = set()
    if no_catalog:
        print("[WARN] --no-catalog：跳过 qoderclicn --list-models，Qoder 侧只含 settings 自定义 provider")
    else:
        catalog = get_catalog()
        if catalog is None:
            print("[WARN] 拿不到模型目录（qoderclicn --list-models 失败），系统/BYOK 项跳过")
        else:
            qoder |= collect_catalog_names(catalog)
    custom, warn = get_settings_models()
    if warn:
        print("[WARN] %s" % warn)
    else:
        qoder |= custom

    if not os.path.exists(roster_path):
        print("[WARN] 花名册不存在，两向对账无法完成: %s" % roster_path)
        return 0
    try:
        data = load_roster(roster_path)
    except Exception as e:
        print("[WARN] 花名册读取/解析失败，两向对账无法完成: %s" % e)
        return 0

    roster = roster_model_names(data)
    qoder_only = sorted(qoder - roster)   # Qoder 有、花名册无 = 待登记候选
    roster_only = sorted(roster - qoder)  # 花名册有、Qoder 无 = 残留待删候选

    print("花名册: %s" % roster_path)
    print("")
    print("[1] Qoder 有、花名册无（待登记候选） %d 个:" % len(qoder_only))
    for n in qoder_only:
        print("  - %s" % n)
    if not qoder_only:
        print("  （无）")
    print("[2] 花名册有、Qoder 无（残留待删候选） %d 个:" % len(roster_only))
    for n in roster_only:
        print("  - %s" % n)
    if not roster_only:
        print("  （无）")
    print("")
    print("--menu 只报告不判失败（退出码恒 0）；settings.json/providers 缺失已按 WARN 跳过。")
    return 0


def main():
    args = sys.argv[1:]
    no_catalog = "--no-catalog" in args
    menu = "--menu" in args
    paths = [a for a in args if not a.startswith("--")]
    roster_path = paths[0] if paths else USER_ROSTER

    if menu:
        return menu_report(roster_path, no_catalog=no_catalog)

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