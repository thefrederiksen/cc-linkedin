# -*- coding: utf-8 -*-
"""The one way every verb touches the browser.

Attach to the already-running, already-signed-in Chrome over its remote
debugging port; open ONE background tab; press buttons by keyboard where a late
click could fall through; watch for a native "Open" dialog; hold the browser
lock so two runs never drive the same Chrome at once.

MEASURED
  * Two Playwright clients attached to one Chrome block each other's
    navigations (2026-09-09 14:34: a run from another session was attached and
    every goto from this one timed out at "commit"). So one Chrome = one run at
    a time, enforced by a lock file, and a second run WAITS, it does not fail.
  * A tab created with Target.createTarget(background=true) does not interrupt
    the person using the browser; a tab from ctx.new_page() becomes the active
    tab in their window. A background tab cannot be screenshotted; bring it to
    the front for that one moment.
  * Chrome hosts the Windows file chooser in a helper process; it is found as
    a visible window of class #32770 titled "Open", not as anything on the
    page. WM_CLOSE cancels it. A run that spawned one still fails.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Error as PWError

STATE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "cc-linkedin")
LIVE_BUTTON = re.compile(r"^(Dismiss|Discard|Post|Schedule)$")


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def die(msg):
    print("FAIL " + msg, flush=True)
    sys.exit(1)


# ---------------------------------------------------------------- native dialogs

def open_file_dialogs():
    """Handles of visible native 'Open' file dialogs on this desktop (Windows)."""
    if not hasattr(ctypes, "windll"):
        return []
    user32 = ctypes.windll.user32
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(h, _):
        if not user32.IsWindowVisible(h):
            return True
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(h, cls, 64)
        if cls.value != "#32770":
            return True
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, title, 256)
        if title.value == "Open":
            found.append(int(h))
        return True

    user32.EnumWindows(proc(cb), 0)
    return found


def close_file_dialogs(where):
    """Cancel any native 'Open' dialog (WM_CLOSE) and name the step that spawned it.
    Clean-up, not a fix: the run that spawned one still fails."""
    handles = open_file_dialogs()
    for h in handles:
        ctypes.windll.user32.SendMessageW(h, 0x0010, 0, 0)
    if handles:
        log("NATIVE OPEN DIALOG appeared after %s (hwnd %s); cancelled it" % (where, handles))
    return handles


# ---------------------------------------------------------------- the lock

class BrowserLock(object):
    """One run per Chrome. A second run waits (up to `wait` seconds) and says so."""

    def __init__(self, port, wait=900):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.path = os.path.join(STATE_DIR, "browser-%d.lock" % port)
        self.wait = wait
        self.fd = None

    def _holder(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def __enter__(self):
        deadline = time.time() + self.wait
        told = False
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, json.dumps({"pid": os.getpid(), "argv": sys.argv[1:4],
                                              "since": time.strftime("%Y-%m-%d %H:%M:%S")}).encode())
                os.close(self.fd)
                return self
            except FileExistsError:
                holder = self._holder()
                pid = holder.get("pid")
                if pid and not _pid_alive(pid):
                    log("browser lock held by dead pid %s; taking it over" % pid)
                    os.remove(self.path)
                    continue
                if not told:
                    log("waiting for the browser: another run holds it (pid %s since %s, %s)"
                        % (pid, holder.get("since"), " ".join(holder.get("argv", []))))
                    told = True
                if time.time() > deadline:
                    die("gave up waiting for the browser after %ds; pid %s still holds it" % (self.wait, pid))
                time.sleep(3)

    def __exit__(self, *exc):
        try:
            os.remove(self.path)
        except OSError:
            pass


def _pid_alive(pid):
    if not hasattr(ctypes, "windll"):
        return True
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return False
    code = wt.DWORD()
    ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(h)
    return bool(ok) and code.value == 259     # STILL_ACTIVE


# ---------------------------------------------------------------- pacing

class Pace(object):
    """Daily caps and gaps for outbound actions, kept in a file so they hold
    across sessions and agents. Reads are never paced."""

    CAPS = {"comment": 60, "react": 100, "connect": 20, "message": 30, "invite": 5}
    GAP = (45, 90)     # seconds between outbound actions, drawn from this range

    def __init__(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.path = os.path.join(STATE_DIR, "pace.json")

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def before(self, kind):
        """Wait out the gap and refuse over the cap. Call right before the action."""
        data = self._load()
        today = time.strftime("%Y-%m-%d")
        day = data.get(today, {})
        n = day.get(kind, 0)
        cap = self.CAPS.get(kind)
        if cap is not None and n >= cap:
            die("daily cap reached for %s (%d today). Tomorrow." % (kind, n))
        last = data.get("last_outbound", 0)
        gap = self.GAP[0] + (hash(str(time.time())) % (self.GAP[1] - self.GAP[0]))
        wait = last + gap - time.time()
        if wait > 0:
            log("pacing: %.0fs before the next %s" % (wait, kind))
            time.sleep(wait)

    def after(self, kind):
        data = self._load()
        today = time.strftime("%Y-%m-%d")
        day = data.setdefault(today, {})
        day[kind] = day.get(kind, 0) + 1
        data["last_outbound"] = time.time()
        for k in [k for k in data if k != "last_outbound" and k < today]:
            del data[k]
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)


# ---------------------------------------------------------------- the tab

class Browser(object):
    """Attach to Chrome on `port`, hold the lock, open one background tab."""

    def __init__(self, port=9224):
        self.port = port
        self._pw = None
        self.browser = None
        self.page = None
        self.lock = BrowserLock(port)

    def __enter__(self):
        if open_file_dialogs():
            die("a native 'Open' file dialog is already on screen; close it first")
        self.lock.__enter__()
        self._pw = sync_playwright().start()
        try:
            self.browser = self._pw.chromium.connect_over_cdp("http://localhost:%d" % self.port, timeout=15000)
        except PWError as exc:
            self.lock.__exit__(None, None, None)
            die("no Chrome is listening on port %d (%s). Start the signed-in profile first, "
                "e.g. bh-profiles.ps1 up cencon" % (self.port, str(exc).splitlines()[0]))
        ctx = self.browser.contexts[0]
        root = self.browser.new_browser_cdp_session()
        with ctx.expect_page(timeout=15000) as opened:
            root.send("Target.createTarget", {"url": "about:blank", "background": True})
        self.page = opened.value
        return self

    def __exit__(self, *exc):
        try:
            if self.page and not self.page.is_closed():
                self.page.close()
        finally:
            try:
                self.browser.close()
            finally:
                self._pw.stop()
                self.lock.__exit__(None, None, None)
                if close_file_dialogs("the run"):
                    die("a native 'Open' file dialog was spawned during the run; cancelled it")

    # -- helpers every verb uses --------------------------------------------

    def goto(self, url, settle=4):
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(settle)
        body = self.page.evaluate("() => document.body ? document.body.innerText.slice(0, 4000) : ''")
        if re.search(r"unusual activity|security verification|let's do a quick security check", body, re.I):
            die("LinkedIn is showing a security check on %s. Stop for today." % url)
        return body

    def press(self, locator, what):
        """Activate a control with the keyboard: focus + Enter. A keystroke cannot
        fall through to whatever is under a dialog that just closed."""
        locator.focus()
        self.page.keyboard.press("Enter")
        log("%s pressed" % what)
        if close_file_dialogs(what):
            die("%s spawned a native file dialog" % what)

    def type_text(self, text):
        """Keystrokes with one Enter per newline; insertText per run."""
        for run in re.split(r"(\n+)", text):
            if not run:
                continue
            if run[0] == "\n":
                for _ in range(len(run)):
                    self.page.keyboard.press("Enter")
            else:
                self.page.keyboard.insert_text(run)

    def screenshot(self, path):
        self.page.bring_to_front()
        time.sleep(1)
        self.page.screenshot(path=path)
