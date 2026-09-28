# -*- coding: utf-8 -*-
"""一次性验收脚本：无头 Edge 验 花名册管理.html 渲染（不碰用户浏览器）。
截图/DOM 输出到 %TEMP%，每次全新 --user-data-dir（防串页）。
"""
import os, re, subprocess, sys, time, threading, urllib.request
from pathlib import Path
from urllib.parse import quote

SKILL = Path(__file__).resolve().parents[2]           # smart-subagent/
HTML = Path(__file__).resolve().parent / "花名册管理.html"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
TMP = Path(os.environ["TEMP"])
API = "http://127.0.0.1:8765"

srv = subprocess.Popen([sys.executable, str(SKILL / "tools" / "roster-admin" / "server.py")],
                       cwd=str(SKILL), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
stop = threading.Event()
def hb():
    while not stop.is_set():
        try: urllib.request.urlopen(API + "/api/heartbeat", timeout=5).read()
        except Exception: pass
        stop.wait(4)
threading.Thread(target=hb, daemon=True).start()
for _ in range(30):
    try:
        urllib.request.urlopen(API + "/api/heartbeat", timeout=3); break
    except Exception: time.sleep(0.5)

def edge(args, out):
    prof = TMP / ("edge-prof-" + str(int(time.time() * 1000) % 100000))
    cmd = [str(EDGE), "--headless", "--disable-gpu", "--no-first-run",
           "--user-data-dir=" + str(prof)] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                       encoding="utf-8", errors="replace")
    return r

url = "file:///" + quote(str(HTML).replace("\\", "/"), safe=":/")

# 1) DOM 验收
dom_file = TMP / "roster-ui-dom.html"
r = edge(["--dump-dom", "--window-size=1280,2400", "--virtual-time-budget=9000", url], dom_file)
dom = r.stdout or ""
dom_file.write_text(dom, encoding="utf-8")
print("DOM bytes:", len(dom))
conn = re.search(r'id="conn"[^>]*>([^<]*)<', dom)
print("conn pill:", conn.group(1) if conn else "(未找到)")
print("models 行数:", len(re.findall(r'class="mono f-alias"', dom)))
print("provider 卡片数:", len(re.findall(r'<h3>qoder-custom-', dom)))
print("agent 行数:", len(re.findall(r'class="mono a-name"', dom)))
print("routing 行数:", len(re.findall(r'class="mono r-cat"', dom)))
pin = re.search(r'qoder-custom-21fa3498[^<]*', dom)
print("钉桩显示:", pin.group(0)[:80] if pin else "(未找到)")
logm = re.search(r'id="log"[^>]*>(.*?)</div>', dom, re.S)
print("日志:", (logm.group(1).strip()[:120] if logm else "(无)"))

# 2) 截图辅证
shot = TMP / "roster-ui.png"
if shot.exists(): shot.unlink()
r = edge(["--screenshot=" + str(shot), "--window-size=1280,2400",
          "--virtual-time-budget=9000", url], None)
print("screenshot:", shot, shot.stat().st_size if shot.exists() else "缺失")

stop.set(); srv.terminate()
try:
    import PIL.Image as I
    im = I.open(shot)
    px = im.convert("L").resize((32, 32))
    mean = sum(px.getdata()) / 1024
    print("图像:", im.size, "灰度均值:", round(mean, 1), "(>100 亮页=正常)")
except Exception as e:
    print("PIL 不可用:", e)
