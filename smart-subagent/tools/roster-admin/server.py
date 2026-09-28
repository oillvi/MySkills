#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""smart-subagent 花名册管理后端（roster-admin）

只绑 127.0.0.1:8765。页面（花名册管理.html）心跳保活；最后一个页面关闭约 12 秒后自退。
写盘前一律 .bak.<时间戳> 备份（每文件各留最近 10 份）。

端点:
  GET  /                    同目录 花名册管理.html
  GET  /api/state           花名册 + settings providers（key 打码） + agents/*.md 钉桩
  POST /api/check           {menu: bool, no_catalog: bool} 跑 tools/check-roster.py
  POST /api/ping            {providerKey, model} 探活（GET /models，失败再试最小 chat）
  POST /api/reveal          {providerKey} 明文 key（仅本机回显用）
  POST /api/save-roster     {models, agents, routing, on_out_of_roster} 外科式改 roster.yml
  POST /api/save-provider   {providerKey, baseUrl?, apiKey?, modelsAdd?, modelsRemove?, isNew?}
                            改 ~/.qoder-cn/settings.json 的 providers（key 留空=不改）
  GET  /api/heartbeat       保活
  POST /api/goodbye         关页信号（3 秒后自退，新心跳可取消）

CLI:
  python server.py --install     注册 roster-admin:// 协议（HKCU，免提权）
  python server.py --uninstall   注销协议
"""
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent                 # tools/roster-admin
SKILL_DIR = HERE.parent.parent                        # smart-subagent（真身=本仓）
USER_HOME = Path(os.environ.get("USERPROFILE", str(Path.home())))
SKILLS_LINK = USER_HOME / ".qoder-cn" / "skills" / "smart-subagent"
ROSTER_PATH = SKILLS_LINK / "roster.yml"              # 生效位（junction → 本仓真身）
AGENTS_DIR = SKILLS_LINK / "agents"
SETTINGS_PATH = USER_HOME / ".qoder-cn" / "settings.json"
CHECK_ROSTER = SKILL_DIR / "tools" / "check-roster.py"

HOST, PORT = "127.0.0.1", 8765
KEEP_BACKUPS = 10

# ---- 心跳/自退 ----
START_TS = time.monotonic()
LAST_HB = [None]          # None=尚无页面
GOODBYE = [False]
INFLIGHT = [0]

# ======================================================================
# 通用小工具
# ======================================================================

def backup_file(path: Path) -> Path:
    """写盘前备份 <file>.bak.<ts>，只留最近 KEEP_BACKUPS 份。"""
    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = path.with_name(path.name + ".bak." + ts)
    shutil.copy2(path, bak)
    baks = sorted(path.parent.glob(path.name + ".bak.*"))
    for old in baks[:-KEEP_BACKUPS]:
        try:
            old.unlink()
        except OSError:
            pass
    return bak


def atomic_write(path: Path, text: str):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def scalar(v) -> str:
    """Python 标量 → YAML 标量文本（能裸写就裸写，否则 JSON 引号）。"""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if re.fullmatch(r"[A-Za-z0-9_\-一-鿿][A-Za-z0-9_\-一-鿿\.\+\(\)（）\[\]\/,，、；;：:\s]*", s) \
            and ": " not in s and not s.endswith(" "):
        return s
    return json.dumps(s, ensure_ascii=False)


def unscalar(text: str):
    text = text.strip()
    try:
        import yaml
        return yaml.safe_load(text)
    except Exception:
        return text

# ======================================================================
# roster.yml 外科式文本编辑（保注释、保顺序；只动条目块与目标行）
# ======================================================================

SEC_RE = re.compile(r"^(models|agents|routing|on_out_of_roster):")


def section_ranges(lines):
    """返回 {段名: (start, end)}，end 不含；start 指向 'xxx:' 那行。"""
    ranges = {}
    cur = None
    for i, ln in enumerate(lines):
        m = SEC_RE.match(ln)
        if m:
            if cur:
                ranges[cur] = (ranges[cur][0], i)
            cur = m.group(1)
            ranges[cur] = (i, len(lines))
    return ranges


def entry_blocks(lines, start, end, prefix_re):
    """段内条目块行区间列表 [(s, e)]，prefix_re 匹配 '  - ' 起始行。"""
    blocks = []
    cur = None
    for i in range(start + 1, end):
        if prefix_re.match(lines[i]):
            if cur:
                blocks.append((cur, i))
            cur = i
    if cur:
        blocks.append((cur, end))
    return blocks


FIELD_RE = re.compile(r"^(  - |    )([A-Za-z_]+):(.*)$")   # 含块首 '  - alias: …'


def block_fields(lines, s, e):
    out = {}
    for i in range(s, e):
        m = FIELD_RE.match(lines[i])
        if m:
            out[m.group(2)] = (i, unscalar(m.group(3)))
    return out


def set_field(lines, s, e, key, value):
    """改条目块内字段（含块首字段）；值没变就一字不动（保住行尾注释）；
    变了则改写该行并保留行尾注释；缺则插到块尾。"""
    fields = block_fields(lines, s, e)
    if key in fields:
        idx, old_val = fields[key]
        if str(old_val) == str(value):
            return
        old = lines[idx]
        prefix = FIELD_RE.match(old).group(1)
        comment = re.search(r"\s+#.*$", old)
        lines[idx] = "%s%s: %s%s" % (prefix, key, scalar(value),
                                     comment.group(0) if comment else "")
    else:
        idx = max(fields[k][0] for k in fields) + 1 if fields else s + 1
        lines.insert(idx, "    %s: %s" % (key, scalar(value)))


def delete_field(lines, s, e, key):
    """删条目块内某字段行（payload 里没有 = 删掉）。块首字段不在此列。"""
    fields = block_fields(lines, s, e)
    if key in fields:
        del lines[fields[key][0]]


def make_entry(prefix, fields):
    out = [prefix]
    for k, v in fields.items():
        out.append("    %s: %s" % (k, scalar(v)))
    return out


def trim_append_point(lines, s, e):
    """条目追加位置：段尾，跳过尾部空行/注释行（注释属于下一个段首）。"""
    i = e
    while i - 1 > s and (lines[i - 1].strip() == "" or lines[i - 1].lstrip().startswith("#")):
        i -= 1
    return i


def find_entry(lines, sec, prefix_re, key, value):
    """每次操作前重扫条目块坐标——行号会因增删漂移，缓存坐标必错。"""
    rng = section_ranges(lines)
    if sec not in rng:
        return None
    s, e = rng[sec]
    for bs, be in entry_blocks(lines, s, e, prefix_re):
        f = block_fields(lines, bs, be)
        if key in f and str(f[key][1]) == str(value):
            return bs, be
    return None


ALIASENTRY = re.compile(r"^  - alias:")
NAMEENTRY = re.compile(r"^  - name:")


def edit_roster(text: str, models, agents, routing, oor) -> str:
    """全量 diff：upsert 给定条目、删除缺席条目。返回新文本（未写盘）。"""
    import yaml
    lines = text.splitlines()
    rng = section_ranges(lines)

    # --- models ---
    s, e = rng["models"]
    blocks = entry_blocks(lines, s, e, re.compile(r"^  - alias:"))
    existing = {}
    for (bs, be) in blocks:
        f = block_fields(lines, bs, be)
        if "alias" in f:
            existing[str(f["alias"][1])] = (bs, be)
    wanted = {str(m.get("alias")): m for m in models}
    for alias, (bs, be) in sorted(existing.items(), key=lambda kv: -kv[1][0]):
        if alias not in wanted:
            del lines[bs:be]
    for m in models:
        alias = str(m.get("alias"))
        fields = {k: v for k, v in m.items() if v not in (None, "") and k != "alias"}
        if find_entry(lines, "models", ALIASENTRY, "alias", alias):
            for k, v in fields.items():
                hit = find_entry(lines, "models", ALIASENTRY, "alias", alias)
                set_field(lines, hit[0], hit[1], k, v)
            for k in ("ref", "kind", "note"):       # payload 缺 = 删（块首 alias 永不动）
                if k not in fields:
                    hit = find_entry(lines, "models", ALIASENTRY, "alias", alias)
                    if hit:
                        delete_field(lines, hit[0], hit[1], k)
        else:
            rng = section_ranges(lines)
            s, e = rng["models"]
            at = trim_append_point(lines, s, e)
            lines[at:at] = make_entry("  - alias: " + scalar(alias), fields)

    # --- agents ---
    rng = section_ranges(lines)
    s, e = rng["agents"]
    blocks = entry_blocks(lines, s, e, re.compile(r"^  - name:"))
    existing = {}
    for (bs, be) in blocks:
        f = block_fields(lines, bs, be)
        if "name" in f:
            existing[str(f["name"][1])] = (bs, be)
    wanted_a = {str(a.get("name")): a for a in agents}
    for name, (bs, be) in sorted(existing.items(), key=lambda kv: -kv[1][0]):
        if name not in wanted_a:
            del lines[bs:be]
    rng = section_ranges(lines)
    s, e = rng["agents"]
    blocks = entry_blocks(lines, s, e, re.compile(r"^  - name:"))
    cur = {str(block_fields(lines, bs, be).get("name", (0, ""))[1]): (bs, be) for bs, be in blocks}
    for a in agents:
        name = str(a.get("name"))
        fields = {k: v for k, v in a.items() if v not in (None, "") and k != "name"}
        if find_entry(lines, "agents", NAMEENTRY, "name", name):
            for k, v in fields.items():
                hit = find_entry(lines, "agents", NAMEENTRY, "name", name)
                set_field(lines, hit[0], hit[1], k, v)
            for k in ("uses", "class", "use_for"):
                if k not in fields:
                    hit = find_entry(lines, "agents", NAMEENTRY, "name", name)
                    if hit:
                        delete_field(lines, hit[0], hit[1], k)
        else:
            rng = section_ranges(lines)
            s, e = rng["agents"]
            at = trim_append_point(lines, s, e)
            lines[at:at] = make_entry("  - name: " + scalar(name), fields)

    # --- routing ---
    rng = section_ranges(lines)
    s, e = rng["routing"]
    have = {}
    for i in range(s + 1, e):
        m = re.match(r"^  ([A-Za-z0-9_\-]+):(.*)$", lines[i])
        if m:
            have[m.group(1)] = i
    for cat in sorted(have, key=lambda k: -have[k]):
        if cat not in routing or routing[cat] in (None, ""):
            del lines[have[cat]]
    rng = section_ranges(lines)
    s, e = rng["routing"]
    have = {}
    for i in range(s + 1, e):
        m = re.match(r"^  ([A-Za-z0-9_\-]+):(.*)$", lines[i])
        if m:
            have[m.group(1)] = i
    for cat, agent in routing.items():
        if agent in (None, ""):
            continue
        rng = section_ranges(lines)
        s, e = rng["routing"]
        idx = None
        for i in range(s + 1, e):                      # 每次重扫，行号会漂
            m = re.match(r"^  ([A-Za-z0-9_\-]+):(.*)$", lines[i])
            if m and m.group(1) == cat:
                idx = i
                break
        if idx is not None:
            old_val = unscalar(re.sub(r"\s+#.*$", "", lines[idx].split(":", 1)[1]))
            if str(old_val) != str(agent):
                comment = re.search(r"\s+#.*$", lines[idx])
                lines[idx] = "  %s: %s%s" % (cat, scalar(agent),
                                             comment.group(0) if comment else "")
        else:
            at = trim_append_point(lines, s, e)
            lines.insert(at, "  %s: %s" % (cat, scalar(agent)))

    # --- on_out_of_roster ---
    for i, ln in enumerate(lines):
        if ln.startswith("on_out_of_roster:"):
            old_val = unscalar(re.sub(r"\s+#.*$", "", ln.split(":", 1)[1]))
            if str(old_val) != str(oor):
                comment = re.search(r"\s+#.*$", ln)
                lines[i] = "on_out_of_roster: %s%s" % (scalar(oor),
                                                       comment.group(0) if comment else "")
            break

    out = "\n".join(lines) + "\n"
    parsed = yaml.safe_load(out)          # 写盘前自检
    assert isinstance(parsed.get("models"), list), "models 段解析失败"
    assert isinstance(parsed.get("agents"), list), "agents 段解析失败"
    for m in parsed["models"]:
        assert m.get("alias") and m.get("ref") and m.get("kind"), "模型条目缺字段: %s" % m
    for a in parsed["agents"]:
        assert a.get("name") and a.get("uses"), "agent 条目缺字段: %s" % a
    return out

# ======================================================================
# settings.json providers（只动 baseUrl/apiKey/models 名单，其余字段原样保留）
# ======================================================================

def provider_view(providers: dict) -> dict:
    """给前端的视图：key 打码，不回传明文。"""
    out = {}
    for k, v in (providers or {}).items():
        v = v or {}
        key = str(v.get("apiKey") or "")
        masked = ("*" * 8 + key[-4:]) if len(key) >= 8 else ("有" if key else "无")
        out[k] = {
            "baseUrl": v.get("baseUrl") or "",
            "keyMasked": masked,
            "hasKey": bool(key),
            "models": [str(mm.get("model")) for mm in (v.get("models") or []) if (mm or {}).get("model")],
        }
    return out


def norm_provider_key(providers: dict, key: str) -> str:
    """settings.json 的 provider 键带 qoder-custom- 前缀，ref 里是裸 UUID——两式都认。"""
    key = str(key or "").strip()
    if key in providers:
        return key
    alt = "qoder-custom-" + key
    return alt if alt in providers else key


def load_settings():
    if not SETTINGS_PATH.exists():
        return None, "settings.json 不存在: %s" % SETTINGS_PATH
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f), None
    except Exception as e:
        return None, "settings.json 解析失败: %s" % e


def save_provider(patch: dict):
    cfg, err = load_settings()
    if err:
        raise RuntimeError(err)
    providers = cfg.setdefault("providers", {})
    key = norm_provider_key(providers, patch.get("providerKey"))
    if not key:
        raise ValueError("缺 providerKey")
    pv = providers.get(key)
    if pv is None:
        if not patch.get("isNew"):
            raise ValueError("provider 不存在: %s（要新建请带 isNew）" % key)
        pv = {}
        providers[key] = pv
    if patch.get("baseUrl"):
        pv["baseUrl"] = str(patch["baseUrl"]).strip()
    if patch.get("apiKey"):
        pv["apiKey"] = str(patch["apiKey"])
    models = pv.setdefault("models", [])
    names = {(mm or {}).get("model") for mm in models}
    for n in patch.get("modelsAdd") or []:
        if n not in names:
            models.append({"model": str(n)})
            names.add(n)
    for n in patch.get("modelsRemove") or []:
        models[:] = [mm for mm in models if (mm or {}).get("model") != n]
    backup_file(SETTINGS_PATH)
    atomic_write(SETTINGS_PATH, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    cfg2, err2 = load_settings()
    if err2:
        raise RuntimeError("写后自检失败: " + err2)
    return provider_view(cfg2.get("providers") or {})

# ======================================================================
# check-roster / 探活
# ======================================================================

def run_check(menu=False, no_catalog=False):
    args = [sys.executable, str(CHECK_ROSTER)]
    if menu:
        args.append("--menu")
    if no_catalog:
        args.append("--no-catalog")
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=180,
                             cwd=str(SKILL_DIR))
    except Exception as e:
        return {"exit": 2, "output": "check-roster 执行失败: %s" % e}
    return {"exit": out.returncode, "output": (out.stdout or "") + (out.stderr or "")}


def http_call(url, method, body=None, key=None, timeout=30):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if key:
        req.add_header("Authorization", "Bearer " + key)
    if data:
        req.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            return resp.status, round(time.time() - t0, 2), resp.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, round(time.time() - t0, 2), exc.read(2000).decode("utf-8", "replace")
    except Exception as exc:
        return type(exc).__name__, round(time.time() - t0, 2), str(exc)[:400]


def ping(base_url: str, api_key: str, model: str):
    """GET /models 先探；不通再发一条最小 chat。两步都不 200 = 不通。"""
    if not base_url:
        return {"ok": False, "status": "no-baseurl", "latency": 0,
                "detail": "该模型无 baseURL（系统/BYOK 模型），探活跳过"}
    base = base_url.rstrip("/")
    st, dur, body = http_call(base + "/models", "GET", key=api_key, timeout=30)
    if st == 200:
        return {"ok": True, "status": st, "latency": dur, "detail": body[:300]}
    st2, dur2, body2 = http_call(base + "/chat/completions", "POST",
                                 body={"model": model,
                                       "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                                       "max_tokens": 8},
                                 key=api_key, timeout=60)
    ok = (st2 == 200)
    return {"ok": ok, "status": st2, "latency": dur2,
            "detail": ("GET /models -> %s (%ss)\n" % (st, dur)) + body2[:400]}

# ======================================================================
# 协议注册（roster-admin:// → launcher.vbs）
# ======================================================================

def protocol_cmd() -> str:
    return 'wscript.exe "%s" "%%1"' % (HERE / "launcher.vbs")


def install_protocol():
    import winreg
    base = r"Software\Classes\roster-admin"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:Roster Admin")
        winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, protocol_cmd())
    print("已注册 roster-admin://  → ", protocol_cmd())


def uninstall_protocol():
    import winreg

    def drop(path):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        except OSError:
            pass

    drop(r"Software\Classes\roster-admin\shell\open\command")
    drop(r"Software\Classes\roster-admin\shell\open")
    drop(r"Software\Classes\roster-admin\shell")
    drop(r"Software\Classes\roster-admin")
    print("已注销 roster-admin://")

# ======================================================================
# HTTP 层
# ======================================================================

class Handler(BaseHTTPRequestHandler):
    server_version = "roster-admin/1.0"

    def log_message(self, fmt, *args):   # 静默访问日志
        pass

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def do_OPTIONS(self):
        self._send(204, b"")

    # ---------- GET ----------
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            html = (HERE / "花名册管理.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
        elif path == "/api/state":
            self._json(200, build_state())
        elif path == "/api/heartbeat":
            LAST_HB[0] = time.monotonic()
            GOODBYE[0] = False
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not found"})

    # ---------- POST ----------
    def do_POST(self):
        path = self.path.split("?", 1)[0]
        LAST_HB[0] = time.monotonic()
        INFLIGHT[0] += 1
        try:
            if path == "/api/goodbye":
                GOODBYE[0] = True
                self._json(200, {"ok": True})
            elif path == "/api/check":
                b = self._body()
                self._json(200, run_check(menu=bool(b.get("menu")),
                                          no_catalog=bool(b.get("no_catalog"))))
            elif path == "/api/ping":
                b = self._body()
                cfg, err = load_settings()
                provs = (cfg or {}).get("providers") or {}
                prov = provs.get(norm_provider_key(provs, b.get("providerKey"))) or {}
                res = ping(str(prov.get("baseUrl") or ""), str(prov.get("apiKey") or ""),
                           str(b.get("model") or ""))
                self._json(200, res)
            elif path == "/api/reveal":
                b = self._body()
                cfg, err = load_settings()
                if err:
                    raise RuntimeError(err)
                provs = (cfg or {}).get("providers") or {}
                prov = provs.get(norm_provider_key(provs, b.get("providerKey"))) or {}
                self._json(200, {"apiKey": str(prov.get("apiKey") or "")})
            elif path == "/api/save-roster":
                b = self._body()
                text = ROSTER_PATH.read_text(encoding="utf-8")
                new_text = edit_roster(text, b.get("models") or [], b.get("agents") or [],
                                       b.get("routing") or {}, b.get("on_out_of_roster") or "report")
                bak = backup_file(ROSTER_PATH)
                atomic_write(ROSTER_PATH, new_text)
                check = run_check(no_catalog=True)
                self._json(200, {"ok": True, "backup": str(bak), "check": check})
            elif path == "/api/save-provider":
                self._json(200, {"ok": True, "providers": save_provider(self._body())})
            else:
                self._json(404, {"error": "not found"})
        except Exception as e:
            self._json(400, {"error": "%s: %s" % (type(e).__name__, e)})
        finally:
            INFLIGHT[0] -= 1


def build_state():
    import yaml
    roster = yaml.safe_load(ROSTER_PATH.read_text(encoding="utf-8")) or {}
    cfg, err = load_settings()
    pins = {}
    if AGENTS_DIR.exists():
        for md in sorted(AGENTS_DIR.glob("*.md")):
            m = re.search(r"^model:\s*(.+)$", md.read_text(encoding="utf-8"), re.M)
            if m:
                pins[md.stem] = m.group(1).strip()
    baks = sorted(p.name for p in ROSTER_PATH.parent.glob(ROSTER_PATH.name + ".bak.*"))
    return {
        "roster_path": str(ROSTER_PATH),
        "settings_path": str(SETTINGS_PATH),
        "roster": {
            "models": roster.get("models") or [],
            "agents": roster.get("agents") or [],
            "routing": roster.get("routing") or {},
            "on_out_of_roster": roster.get("on_out_of_roster") or "report",
        },
        "providers": provider_view((cfg or {}).get("providers") or {}),
        "settings_error": err,
        "agent_pins": pins,
        "backups": baks[-5:],
    }


def watchdog():
    while True:
        time.sleep(1)
        now = time.monotonic()
        if INFLIGHT[0] > 0:
            continue
        if LAST_HB[0] is not None:
            idle = now - LAST_HB[0]
            if (GOODBYE[0] and idle > 3) or idle > 12:
                os._exit(0)
        elif now - START_TS > 90:      # 协议唤起后页面没接上
            os._exit(0)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--install":
        return install_protocol()
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        return uninstall_protocol()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, PORT))
        except OSError:
            print("端口 %d 已被占用，视为已有实例在跑，本进程退出。" % PORT)
            return                       # 已有实例在跑

    threading.Thread(target=watchdog, daemon=True).start()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print("roster-admin 已启动: http://%s:%d/  （页面心跳保活，关页 12 秒内自退）" % (HOST, PORT))
    httpd.serve_forever()


if __name__ == "__main__":
    main()
