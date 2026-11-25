# -*- coding: utf-8 -*-
"""devthrottle#4916: the attach must not wait on the tabs that were already open
in the shared profile.

THE DEFECT. Browser.__enter__ called connect_over_cdp("http://localhost:9224")
straight at Chrome. Playwright then auto-attaches to every existing target and
waits until every existing page answers about fifteen commands from its own
renderer. Background tabs run at idle priority on Windows and starve on a busy
machine, so with 40 background tabs and every core busy the attach took 35-79s
and the LinkedIn station lost whole runs to the 90s timeout (2026-10-27,
2026-11-19, 2026-11-20).

THE FIX, as tested here. Playwright is handed the ws:// url of a local
TargetHidingProxy. The proxy snapshots the target ids that exist before
Playwright connects; when Chrome auto-attaches one of them the proxy detaches
it again itself and Playwright never hears of it. A target created later passes.

What these tests can and cannot prove. They run with no browser: the filter is
tested on its own, and the proxy is tested end to end against a FAKE Chrome - a
local websocket server that speaks just enough CDP. That proves the proxy hides
pre-existing targets and passes new ones. The timing claim - that a real
attach no longer depends on how many starved tabs the profile holds - cannot be
proved offline; it was measured live against cencon and against a throwaway
Chrome with tools/attach_bench.py, and the numbers are on the pull request.
"""
import json
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from websockets.sync.client import connect as ws_connect
from websockets.sync.server import serve as ws_serve

from cc_linkedin_kit import browser as B
from cc_linkedin_kit import cdp_proxy as P
from tests.test_attach import AttachCase

EXISTING = ["OLD-PAGE-1", "OLD-PAGE-2", "OLD-SW"]


def attached(target, session, kind="page"):
    return {"method": "Target.attachedToTarget",
            "params": {"sessionId": session, "waitingForDebugger": False,
                       "targetInfo": {"targetId": target, "type": kind}}}


class TheFilter(unittest.TestCase):

    def setUp(self):
        self.f = P.HiddenTargets(EXISTING)

    def test_an_existing_target_is_detached_and_never_reported(self):
        forward, cmds = self.f.from_browser(attached("OLD-PAGE-1", "S1"))
        self.assertFalse(forward)
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0]["method"], "Target.detachFromTarget")
        self.assertEqual(cmds[0]["params"], {"sessionId": "S1"})
        self.assertTrue(P.HiddenTargets.is_own_id(cmds[0]["id"]))

    def test_a_new_target_passes_untouched(self):
        # the control: if everything were hidden the working tab would never
        # report in and open_working_tab would die
        self.assertEqual(self.f.from_browser(attached("OUR-TAB", "S9")), (True, []))

    def test_what_a_hidden_session_says_is_dropped(self):
        self.f.from_browser(attached("OLD-PAGE-2", "S2"))
        self.assertEqual(self.f.from_browser(
            {"sessionId": "S2", "method": "Runtime.executionContextCreated", "params": {}}),
            (False, []))
        self.assertEqual(self.f.from_browser(
            {"method": "Target.detachedFromTarget", "params": {"sessionId": "S2"}}),
            (False, []))

    def test_the_reply_to_our_own_detach_is_dropped(self):
        _, cmds = self.f.from_browser(attached("OLD-SW", "S3", "service_worker"))
        self.assertEqual(self.f.from_browser({"id": cmds[0]["id"], "result": {}}), (False, []))

    def test_playwright_replies_and_other_events_pass(self):
        self.assertEqual(self.f.from_browser({"id": 7, "result": {}}), (True, []))
        self.assertEqual(self.f.from_browser(
            {"method": "Target.detachedFromTarget", "params": {"sessionId": "S9"}}), (True, []))
        # an iframe of OUR tab attaches inside our tab's session: it passes even
        # if, by some id reuse, it matched the hidden set
        msg = attached("OLD-PAGE-1", "CHILD")
        msg["sessionId"] = "OUR-SESSION"
        self.assertEqual(self.f.from_browser(msg), (True, []))


class FakeChrome(object):
    """Just enough of Chrome's browser endpoint: /json/version over HTTP, and on
    the websocket Target.getTargets, Target.setAutoAttach (which reports the
    existing targets and one new one, the way Chrome does), and
    Target.detachFromTarget."""

    def __init__(self):
        self.detached = []
        self.seen = []
        self.server = ws_serve(self.handle, "127.0.0.1", 0, process_request=self.http)
        self.port = self.server.socket.getsockname()[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def http(self, connection, request):
        if request.path == "/json/version":
            body = json.dumps({"webSocketDebuggerUrl":
                               "ws://127.0.0.1:%d/devtools/browser/fake" % self.port})
            return connection.respond(200, body)
        return None

    def handle(self, ws):
        sessions = {}
        for text in ws:
            msg = json.loads(text)
            self.seen.append(msg)
            method, mid = msg.get("method"), msg.get("id")
            if method == "Target.getTargets":
                ws.send(json.dumps({"id": mid, "result": {"targetInfos": [
                    {"targetId": t, "type": "page"} for t in EXISTING]}}))
            elif method == "Target.setAutoAttach":
                for i, t in enumerate(EXISTING + ["NEW-TAB"]):
                    sessions["S%d" % i] = t
                    ws.send(json.dumps(attached(t, "S%d" % i)))
                # an event from an existing tab before its detach lands
                ws.send(json.dumps({"sessionId": "S0", "method": "Inspector.detached",
                                    "params": {}}))
                ws.send(json.dumps({"id": mid, "result": {}}))
            elif method == "Target.detachFromTarget":
                sid = msg["params"]["sessionId"]
                self.detached.append(sessions[sid])
                ws.send(json.dumps({"id": mid, "result": {}}))
                ws.send(json.dumps({"method": "Target.detachedFromTarget",
                                    "params": {"sessionId": sid, "targetId": sessions[sid]}}))
            else:
                ws.send(json.dumps({"id": mid, "result": {"echo": method}}))

    def close(self):
        self.server.shutdown()


class TheProxyAgainstAFakeChrome(unittest.TestCase):

    def setUp(self):
        self.chrome = FakeChrome()
        self.addCleanup(self.chrome.close)

    def test_playwright_sees_only_the_new_target(self):
        proxy = P.TargetHidingProxy(self.chrome.port)
        url = proxy.start()
        self.addCleanup(proxy.stop)
        self.assertTrue(url.startswith("ws://127.0.0.1:"), url)
        self.assertEqual(proxy.hidden_count, len(EXISTING))
        got = []
        with ws_connect(url) as client:
            client.send(json.dumps({"id": 1, "method": "Target.setAutoAttach",
                                    "params": {"autoAttach": True,
                                               "waitForDebuggerOnStart": True,
                                               "flatten": True}}))
            # Chrome answers in order and the proxy keeps that order, and its
            # detaches go out before the reply to 1 is forwarded, so once the
            # reply to 2 is here every detach and its aftermath has passed
            client.send(json.dumps({"id": 2, "method": "Browser.getVersion"}))
            while True:
                msg = json.loads(client.recv(timeout=5))
                got.append(msg)
                if msg.get("id") == 2:
                    break
        reported = [m["params"]["targetInfo"]["targetId"] for m in got
                    if m.get("method") == "Target.attachedToTarget"]
        self.assertEqual(reported, ["NEW-TAB"])
        self.assertEqual(sorted(self.chrome.detached), sorted(EXISTING))
        self.assertEqual([m for m in got if m.get("sessionId")], [])
        self.assertEqual([m for m in got if m.get("method") == "Target.detachedFromTarget"], [])
        self.assertEqual([m["id"] for m in got if "id" in m], [1, 2])
        # one connection, and it shuts itself down when that connection closes
        deadline = time.time() + 5
        while not proxy._done.is_set() and time.time() < deadline:
            time.sleep(0.02)
        self.assertTrue(proxy._done.is_set(), "the proxy outlived Playwright's disconnect")

    def test_no_chrome_is_an_attach_error_naming_the_port(self):
        self.chrome.close()
        port = self.chrome.port
        with self.assertRaises(P.AttachError) as caught:
            P.TargetHidingProxy(port).start()
        self.assertIn("no Chrome is listening on port %d" % port, str(caught.exception))


class RecordingPlaywright(object):
    def __init__(self, browser):
        self.chromium = self
        self.browser = browser
        self.urls = []

    def connect_over_cdp(self, url, timeout=None):
        self.urls.append((url, timeout))
        return self.browser

    def start(self):
        return self

    def stop(self):
        pass


class TheBrowserAttachesThroughTheProxy(AttachCase):
    """THE DEFECT, as a test. Before the fix Playwright was handed
    http://localhost:<port> and attached to every tab in the profile."""

    def test_playwright_is_handed_the_proxy_not_chrome(self):
        from tests.test_attach import FakeBrowser, FakeSession
        rec = RecordingPlaywright(FakeBrowser(FakeSession()))
        B.sync_playwright = lambda: rec
        br = B.Browser(self.port).__enter__()
        try:
            self.assertEqual(len(rec.urls), 1)
            url, timeout = rec.urls[0]
            self.assertNotIn("localhost:%d" % self.port, url,
                             "Playwright attached straight to Chrome, so it waits on every tab")
            self.assertEqual(url, "ws://127.0.0.1:1/fake-proxy-%d" % self.port)
            self.assertLessEqual(timeout, 15000)
            self.assertIsNotNone(br.proxy)
        finally:
            br.__exit__(None, None, None)
        self.assertTrue(br.proxy.stopped, "the proxy was not stopped at teardown")

    def test_a_failed_attach_stops_the_proxy_and_says_why(self):
        made = []

        def factory(port):
            from tests.test_lock import FakeProxy
            p = FakeProxy(port)
            made.append(p)
            return p
        B.TargetHidingProxy = factory

        class Refusing(RecordingPlaywright):
            def connect_over_cdp(self, url, timeout=None):
                raise B.PWError("Timeout 15000ms exceeded")
        B.sync_playwright = lambda: Refusing(None)
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                B.Browser(self.port).__enter__()
        self.assertTrue(made and made[0].stopped, "a failed attach left the proxy running")
        self.assertNotIn("BUSY profile", out.getvalue())
        self.assertFalse(self.held())


if __name__ == "__main__":
    unittest.main()
