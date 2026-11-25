# -*- coding: utf-8 -*-
"""Attach Playwright to a shared Chrome WITHOUT attaching to the tabs that were
already open in it. devthrottle#4916.

THE DEFECT. Playwright's connect_over_cdp sends Target.setAutoAttach with
waitForDebuggerOnStart on the browser session, so Chrome attaches it to every
target that exists, and for every existing PAGE it then runs about fifteen
commands (Page.enable, Runtime.enable, Network.enable, ...) and waits for ALL of
them, in one Promise.all with no per-page timeout. Most of those need the tab's
own renderer to answer. On Windows a background tab's renderer runs at IDLE
priority and gets no CPU while anything above it wants all of it, so on a busy
machine the attach waits on every starved tab in the profile. Measured on a
throwaway Chrome with 40 background tabs and every core busy: 35s and 79s;
idle, 0.7s for 60 tabs. The cencon profile is shared with other sessions, which
leave their tabs open, and the LinkedIn station lost whole runs to the 90s
attach timeout on 2026-10-27, 2026-11-19 and 2026-11-20.

THE FIX. cc-linkedin only ever drives the one tab it creates. So Playwright is
pointed at this proxy instead of at Chrome. The proxy takes the ids of every
target that exists BEFORE Playwright connects, and when Chrome auto-attaches one
of those it detaches it again itself and never tells Playwright it existed.
Playwright waits for nothing it cannot see. Targets created after the snapshot -
the working tab, its iframes and workers - pass through untouched. Prototype,
same throwaway Chrome, 40 tabs, every core busy: 0.13-0.29s.

Service workers that were running are pre-existing targets too, so they are
hidden like any tab. That retired Browser._stop_service_workers (2026-09-20),
which closed every service worker in the shared profile - other sessions'
included - before each attach: the proxy attach was measured on cencon with
its two service workers left running, 0.09-0.87s under full load.

The proxy serves exactly ONE connection and shuts itself down when that
connection closes, so browser.close() on the Playwright side is the whole of the
clean-up; stop() exists for the paths where Playwright never connected.
"""
import json
import threading
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect as ws_connect
from websockets.sync.server import serve as ws_serve

# Message ids the proxy uses for its own commands on the upstream connection.
# Playwright numbers its commands from 1 upwards on one counter per connection
# and never comes near this; Chrome rejects ids that do not fit a signed 32-bit
# integer, so the range stays below 2**31.
OWN_ID_BASE = 2000000000

# Each of the three steps before Playwright's own attach - the HTTP read of
# /json/version, the websocket open, the Target.getTargets snapshot - may take
# this long. All three answer from the browser process, not from any tab, and
# take milliseconds when it is alive, so the worst case before Playwright's own
# timer starts is 3 x 5s.
STEP_TIMEOUT_S = 5


class AttachError(Exception):
    """The proxy could not be put between Playwright and Chrome.

    `no_chrome` is True only when nothing answered on the port at all - the one
    case where "start the signed-in profile" is the right advice. Every other
    AttachError is a Chrome that IS running and is not answering properly."""

    def __init__(self, message, no_chrome=False):
        Exception.__init__(self, message)
        self.no_chrome = no_chrome


class HiddenTargets(object):
    """The filter, kept apart from the sockets so it can be tested on its own.

    `hidden` is the set of target ids that existed before Playwright connected.
    from_browser() decides what happens to one message coming from Chrome: it
    returns (forward, commands), where `forward` says whether Playwright may see
    it and `commands` are messages the proxy must send to Chrome itself."""

    def __init__(self, hidden):
        self.hidden = set(hidden)
        self.hidden_sessions = set()
        self._next_id = OWN_ID_BASE

    def own_id(self):
        self._next_id += 1
        return self._next_id

    @staticmethod
    def is_own_id(mid):
        return isinstance(mid, int) and mid > OWN_ID_BASE

    def from_browser(self, msg):
        if self.is_own_id(msg.get("id")):
            # the reply to a detach the proxy sent; Playwright never asked
            return False, []
        if msg.get("sessionId") in self.hidden_sessions:
            # anything a hidden target says before its detach lands
            return False, []
        method = msg.get("method")
        params = msg.get("params") or {}
        if "sessionId" in msg:
            # Inside a session Playwright owns (our tab's iframes and workers).
            # Only root-session attaches are the pre-existing targets.
            return True, []
        if method == "Target.attachedToTarget":
            info = params.get("targetInfo") or {}
            if info.get("targetId") in self.hidden:
                session = params.get("sessionId")
                self.hidden_sessions.add(session)
                return False, [{"id": self.own_id(), "method": "Target.detachFromTarget",
                                "params": {"sessionId": session}}]
        if method == "Target.detachedFromTarget" and params.get("sessionId") in self.hidden_sessions:
            return False, []
        return True, []


# 127.0.0.1, NOT localhost. Measured 2026-11-24 on SOREN_NORTH: Chrome's
# DevTools listens on 127.0.0.1 only, and on this machine "localhost" is tried
# as ::1 first, which is refused after 2.0s - every HTTP read and websocket open
# to "localhost:9224" cost 2s before it reached Chrome (0.00s to 127.0.0.1).
DEVTOOLS_HOST = "127.0.0.1"


def browser_ws_url(port):
    """Chrome's browser-level DevTools websocket, read over HTTP. The url
    Chrome gives says "localhost"; it is pointed at DEVTOOLS_HOST instead."""
    try:
        with urlopen("http://%s:%d/json/version" % (DEVTOOLS_HOST, port),
                     timeout=STEP_TIMEOUT_S) as r:
            url = json.loads(r.read().decode("utf-8", "replace"))["webSocketDebuggerUrl"]
    except Exception as exc:                                      # noqa: BLE001
        raise AttachError("no Chrome is listening on port %d (%s)" % (port, _first(exc)),
                          no_chrome=True)
    parts = urlsplit(url)
    return urlunsplit(parts._replace(netloc="%s:%d" % (DEVTOOLS_HOST, parts.port or port)))


def _first(exc):
    text = str(exc)
    return text.splitlines()[0] if text else type(exc).__name__


class TargetHidingProxy(object):
    """One local websocket for Playwright, one upstream to Chrome, the filter
    between them. start() returns the ws:// url to hand to connect_over_cdp."""

    def __init__(self, port):
        self.port = port
        self.filter = None
        self._upstream = None
        self._server = None
        self._send_lock = threading.Lock()
        self._served = False
        self._done = threading.Event()

    # -- lifecycle -----------------------------------------------------------

    def start(self):
        url = browser_ws_url(self.port)
        try:
            self._upstream = ws_connect(url, max_size=None, compression=None,
                                        open_timeout=STEP_TIMEOUT_S, ping_interval=None)
        except Exception as exc:                                  # noqa: BLE001
            raise AttachError("Chrome on port %d answered over HTTP but its DevTools "
                              "websocket would not open (%s)" % (self.port, _first(exc)))
        try:
            self.filter = HiddenTargets(self._snapshot())
            try:
                self._server = ws_serve(self._serve_one, "127.0.0.1", 0, max_size=None,
                                        compression=None, ping_interval=None)
            except OSError as exc:
                raise AttachError("the local proxy for Playwright could not listen on "
                                  "127.0.0.1 (%s)" % _first(exc))
        except BaseException:
            self.stop()
            raise
        threading.Thread(target=self._server.serve_forever, name="cdp-proxy-server",
                         daemon=True).start()
        return "ws://127.0.0.1:%d/" % self._server.socket.getsockname()[1]

    def stop(self):
        """Idempotent. Closes both sides and the listening socket."""
        self._done.set()
        if self._upstream is not None:
            try:
                self._upstream.close()
            except Exception:                                     # noqa: BLE001
                pass
        if self._server is not None:
            server, self._server = self._server, None
            # shutdown() waits for serve_forever to return; never call it on
            # the server's own thread
            threading.Thread(target=server.shutdown, name="cdp-proxy-shutdown",
                             daemon=True).start()

    @property
    def hidden_count(self):
        return len(self.filter.hidden) if self.filter else 0

    # -- the work ------------------------------------------------------------

    def _snapshot(self):
        """Every target id that exists now, from Chrome itself (not /json/list,
        which leaves out some target types). Asked on the upstream connection
        before Playwright is connected, so no other message can arrive.

        Every way this can go wrong is an AttachError, so the caller prints a
        FAIL line and gives the browser lock back: Chrome closing the socket
        here (a profile restarting as a run attaches) used to escape as a
        traceback and, in the posting tool, keep the lock."""
        mid = OWN_ID_BASE
        try:
            self._upstream.send(json.dumps({"id": mid, "method": "Target.getTargets"}))
            while True:
                msg = json.loads(self._upstream.recv(timeout=STEP_TIMEOUT_S))
                if msg.get("id") == mid:
                    break
        except TimeoutError:
            raise AttachError("Chrome on port %d did not list its targets within %ds"
                              % (self.port, STEP_TIMEOUT_S))
        except Exception as exc:                                  # noqa: BLE001
            raise AttachError("Chrome on port %d dropped the DevTools connection while "
                              "listing its targets (%s)" % (self.port, _first(exc)))
        if "error" in msg:
            raise AttachError("Chrome on port %d refused Target.getTargets: %s"
                              % (self.port, msg["error"]))
        try:
            return [t["targetId"] for t in msg["result"]["targetInfos"]]
        except (KeyError, TypeError) as exc:
            raise AttachError("Chrome on port %d answered Target.getTargets with no target "
                              "list (%s)" % (self.port, _first(exc)))

    def _to_browser(self, text):
        with self._send_lock:
            self._upstream.send(text)

    def _serve_one(self, client):
        if self._served:
            client.close(1008, "this proxy serves one connection")
            return
        self._served = True
        pump = threading.Thread(target=self._pump_from_browser, args=(client,),
                                name="cdp-proxy-from-browser", daemon=True)
        pump.start()
        try:
            for text in client:
                self._to_browser(text)
        except ConnectionClosed:
            pass
        finally:
            self.stop()
            pump.join(timeout=5)

    def _pump_from_browser(self, client):
        try:
            for text in self._upstream:
                forward, commands = self.filter.from_browser(json.loads(text))
                for cmd in commands:
                    self._to_browser(json.dumps(cmd))
                if forward:
                    client.send(text)
        except ConnectionClosed:
            pass
        finally:
            try:
                client.close()
            except Exception:                                     # noqa: BLE001
                pass
