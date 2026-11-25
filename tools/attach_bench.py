# -*- coding: utf-8 -*-
"""Measure the CDP attach with many background tabs and a busy machine.
devthrottle#4916.

Opens N background tabs OF ITS OWN in the Chrome on --port (a local test page
with cross-site iframes and a dedicated worker - never LinkedIn), optionally
holds every core with spinners at BELOW_NORMAL priority (above an idle
background renderer, below every normal process), then times:

  * the attach itself, both ways, both at 127.0.0.1 so neither pays the ::1
    penalty "localhost" costs on this machine, holding the browser lock so no other
    cc-linkedin run is disturbed: Playwright straight at Chrome (the old path)
    and through TargetHidingProxy (the fix);
  * any commands given with --cmd, wall time each (for example a read-only
    `cc_linkedin.py read-inbox --limit 5` from the old and the new checkout).

On the way out it stops the load and closes ONLY the tabs it opened, by their
own target ids. Every other tab in the browser is left exactly as it was.

    py -3.11 tools/attach_bench.py --port 9224 --tabs 40 --load --trials 2 \\
        --cmd "py -3.11 D:/old/cc_linkedin.py read-inbox --limit 5"
"""
import argparse
import http.server
import json
import os
import shlex
import subprocess
import sys
import threading
import time
from urllib.request import urlopen

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from websockets.sync.client import connect as ws_connect
from playwright.sync_api import sync_playwright, Error as PWError

from cc_linkedin_kit.browser import BrowserLock, attach_cdp
from cc_linkedin_kit.cdp_proxy import DEVTOOLS_HOST, browser_ws_url

BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

PAGE = """<!doctype html><title>attach-bench</title>
<p id=n>0</p>
<iframe src="http://127.0.0.1:%(port)d/frame?a"></iframe>
<iframe src="http://127.0.0.1:%(port)d/frame?b"></iframe>
<iframe src="http://127.0.0.1:%(port)d/frame?c"></iframe>
<script>
new Worker(URL.createObjectURL(new Blob(
  ["setInterval(()=>{let s=0;for(let i=0;i<2e5;i++)s+=i;postMessage(s)},200)"])));
setInterval(()=>{document.getElementById('n').textContent=Date.now()},100);
</script>"""
FRAME = "<!doctype html><script>setInterval(()=>{document.title=Date.now()},250)</script>"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = (FRAME if self.path.startswith("/frame") else
                PAGE % {"port": self.server.server_address[1]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class Cdp(object):
    def __init__(self, port):
        self.ws = ws_connect(browser_ws_url(port), max_size=None, compression=None, ping_interval=None)
        self.mid = 0

    def call(self, method, params=None):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv(timeout=30))
            if msg.get("id") == self.mid:
                if "error" in msg:
                    raise RuntimeError("%s: %s" % (method, msg["error"]))
                return msg["result"]


def page_count(port):
    return sum(1 for t in json.loads(urlopen("http://%s:%d/json/list" % (DEVTOOLS_HOST, port),
                                             timeout=10).read().decode("utf-8"))
               if t.get("type") == "page")


def live_ids(port):
    return {t.get("id") for t in json.loads(urlopen("http://%s:%d/json/list"
                                                    % (DEVTOOLS_HOST, port),
                                                    timeout=10).read().decode("utf-8"))}


def spinners():
    n = os.cpu_count() or 4
    return [subprocess.Popen([sys.executable, "-c", "while True: pass"],
                             creationflags=BELOW_NORMAL_PRIORITY_CLASS) for _ in range(n)]


def time_attach(port, direct, timeout_ms):
    with BrowserLock(port):
        pw = sync_playwright().start()
        try:
            t0 = time.time()
            try:
                if direct:
                    browser = pw.chromium.connect_over_cdp("http://%s:%d" % (DEVTOOLS_HOST, port),
                                                           timeout=timeout_ms)
                else:
                    browser, _proxy = attach_cdp(pw, port, timeout_ms)
            except PWError as exc:
                return time.time() - t0, None, "FAILED " + str(exc).splitlines()[0][:80]
            took = time.time() - t0
            seen = sum(len(c.pages) for c in browser.contexts)
            browser.close()
            return took, seen, "ok"
        finally:
            pw.stop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9224)
    ap.add_argument("--tabs", type=int, default=40)
    ap.add_argument("--load", action="store_true")
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--direct-timeout", type=int, default=90000)
    ap.add_argument("--cmd", action="append", default=[])
    a = ap.parse_args()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://localhost:%d/page" % server.server_address[1]

    cdp = Cdp(a.port)
    ours, load = [], []
    try:
        print("pages before: %d" % page_count(a.port), flush=True)
        for _ in range(a.tabs):
            ours.append(cdp.call("Target.createTarget",
                                 {"url": url, "background": True})["targetId"])
        time.sleep(5)
        print("opened %d background tabs of our own; pages now: %d"
              % (len(ours), page_count(a.port)), flush=True)
        if a.load:
            load = spinners()
            time.sleep(3)
            print("load: %d BELOW_NORMAL spinners" % len(load), flush=True)
        for i in range(a.trials):
            for direct in (True, False):
                took, seen, how = time_attach(a.port, direct, a.direct_timeout if direct
                                              else 15000)
                print("trial %d %-6s attach %.2fs, pages Playwright saw: %s, %s"
                      % (i + 1, "direct" if direct else "proxy", took, seen, how), flush=True)
        for cmd in a.cmd:
            t0 = time.time()
            r = subprocess.run(shlex.split(cmd, posix=False), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            took = time.time() - t0
            lines = (r.stdout + r.stderr).strip().splitlines()
            fails = [l for l in lines if l.startswith("FAIL")]
            rows = [l for l in lines if l.startswith("{")]
            print("cmd %.2fs exit %d rows %d %s :: %s"
                  % (took, r.returncode, len(rows), fails[:1], cmd), flush=True)
    finally:
        for p in load:
            p.kill()
        closed = 0
        for t in ours:
            try:
                if cdp.call("Target.closeTarget", {"targetId": t}).get("success"):
                    closed += 1
            except RuntimeError:
                pass
        # closeTarget answers before the tab is gone; count once it is
        deadline = time.time() + 15
        while time.time() < deadline and set(ours) & live_ids(a.port):
            time.sleep(0.25)
        print("closed %d of our %d tabs, %d still listed; pages after: %d"
              % (closed, len(ours), len(set(ours) & live_ids(a.port)), page_count(a.port)),
              flush=True)
        server.shutdown()


if __name__ == "__main__":
    main()
