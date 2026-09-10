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
import random
import re
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Error as PWError

STATE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "cc-linkedin")
LIVE_BUTTON = re.compile(r"^(Dismiss|Discard|Post|Schedule)$")
DAY_KEY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# the signed-in identity control, both renderings (see Browser.assert_signed_in)
ME_BUTTON = re.compile(r"(^|\s)Me$")


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
    """One run per Chrome. A second run waits (up to `wait` seconds) and says so.

    RULING R3.3, 2026-09-09. The sentinel is written to a temporary file and then
    LINKED into place, so the file at `self.path` is complete the instant it
    exists. os.link is atomic and fails if the destination is already there,
    which is exactly the claim being made: I have the lock, and here is who I am.

    That matters because of what it makes possible. Before this, the sentinel was
    created empty and then written, so a crash in between left a file that parsed
    as `{}`, carried no pid, was never classified as dead, and was therefore never
    reclaimed by anything: every later session on this machine waited fifteen
    minutes, gave up, and left it in place for the next one. Now that a partial
    sentinel cannot exist, a lock file that will not parse is a BROKEN LOCK and
    is taken over, with a log line saying so.

    Deliberately NOT a grace period. Reclaiming on a timer would let a second run
    steal the lock from a healthy holder that was merely slow, which is worse
    than the bug being fixed.
    """

    def __init__(self, port, wait=900):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.path = os.path.join(STATE_DIR, "browser-%d.lock" % port)
        self.wait = wait

    def _holder(self):
        """(holder, why it is unreadable). A lock we cannot read is broken."""
        try:
            with open(self.path, encoding="utf-8") as f:
                raw = f.read()
        except OSError as exc:
            return None, "it cannot be opened (%s)" % str(exc).splitlines()[0][:60]
        try:
            holder = json.loads(raw)
        except ValueError:
            return None, "it does not parse as JSON (%r)" % raw[:60]
        if not isinstance(holder, dict) or not holder.get("pid"):
            return None, "it names no process (%r)" % raw[:60]
        return holder, None

    def _sentinel(self):
        """A complete lock record in a temporary file, ready to be linked in."""
        fd, tmp = tempfile.mkstemp(prefix="browser-lock-", dir=STATE_DIR)
        try:
            os.write(fd, json.dumps({"pid": os.getpid(), "argv": sys.argv[1:4],
                                     "since": time.strftime("%Y-%m-%d %H:%M:%S")}).encode())
        finally:
            os.close(fd)
        return tmp

    def __enter__(self):
        deadline = time.time() + self.wait
        told = False
        tmp = self._sentinel()
        try:
            while True:
                try:
                    os.link(tmp, self.path)
                    return self
                except FileExistsError:
                    holder, unreadable = self._holder()
                    if unreadable:
                        log("browser lock at %s is BROKEN: %s. A lock record is written whole or "
                            "not at all, so this one cannot be a healthy holder; taking it over."
                            % (self.path, unreadable))
                        _discard(self.path)
                        continue
                    pid = holder.get("pid")
                    if not _pid_alive(pid):
                        log("browser lock held by dead pid %s; taking it over" % pid)
                        _discard(self.path)
                        continue
                    if not told:
                        log("waiting for the browser: another run holds it (pid %s since %s, %s)"
                            % (pid, holder.get("since"), " ".join(holder.get("argv", []))))
                        told = True
                    if time.time() > deadline:
                        die("gave up waiting for the browser after %ds; pid %s still holds it"
                            % (self.wait, pid))
                    time.sleep(3)
        finally:
            _discard(tmp)

    def __exit__(self, *exc):
        _discard(self.path)


def _discard(path):
    try:
        os.remove(path)
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
    """Daily caps and gaps, kept in a file so they hold across sessions and
    agents. TWO TRACKS, and they never touch each other.

      * OUTBOUND - comment, react, connect, message, invite. 45 to 90 seconds
        between actions, because these reach a person.
      * VIEW - a profile or a company page actually opened, and one search
        results page however many cards it holds. 3 to 8 seconds, cap 80 a day.
        High-volume profile viewing is one of the top triggers for an account
        warning, so reads are capped; but a read must not make the next comment
        wait 90 seconds, and a page of 25 search results must not take an hour.

    The gap is DRAWN from its range with random.uniform. It used to be
    `hash(str(time.time())) % span`, which is not random in any useful sense -
    CPython's hash of a string is deterministic within a run and the low bits of
    a timestamp string are close to uniform only by accident. A rhythm that
    looks fixed is exactly what pattern detection is for.
    """

    CAPS = {"comment": 60, "react": 100, "connect": 20, "message": 30, "invite": 5}
    GAP = (45, 90)         # seconds between outbound actions
    VIEW_CAP = 80          # profile/company/search pages opened per day
    VIEW_GAP = (3, 8)      # seconds between reads

    def __init__(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.path = os.path.join(STATE_DIR, "pace.json")

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data):
        today = time.strftime("%Y-%m-%d")
        for k in [k for k in data if DAY_KEY.match(k) and k < today]:
            del data[k]
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)

    def count(self, kind, when=None):
        """How many of `kind` have been done today. Used by the selftest to prove
        the view counter moved by exactly the number of views the run took."""
        day = self._load().get(when or time.strftime("%Y-%m-%d"), {})
        return day.get(kind, 0)

    # -- outbound -----------------------------------------------------------

    def before(self, kind):
        """Wait out the gap and refuse over the cap. Call right before the action."""
        data = self._load()
        n = data.get(time.strftime("%Y-%m-%d"), {}).get(kind, 0)
        cap = self.CAPS.get(kind)
        if cap is not None and n >= cap:
            die("daily cap reached for %s (%d today). Tomorrow." % (kind, n))
        self._wait(data.get("last_outbound", 0), self.GAP, kind)

    def after(self, kind):
        data = self._load()
        day = data.setdefault(time.strftime("%Y-%m-%d"), {})
        day[kind] = day.get(kind, 0) + 1
        data["last_outbound"] = time.time()
        self._save(data)

    # -- views --------------------------------------------------------------

    def before_view(self, what="page"):
        """One view = one profile, one company page, or one page of search
        results. Refuses over the daily cap; never touches the outbound clock."""
        data = self._load()
        n = data.get(time.strftime("%Y-%m-%d"), {}).get("view", 0)
        if n >= self.VIEW_CAP:
            die("daily cap reached for views (%d today, cap %d). Tomorrow." % (n, self.VIEW_CAP))
        self._wait(data.get("last_view", 0), self.VIEW_GAP, "view of %s" % what)

    def after_view(self):
        data = self._load()
        day = data.setdefault(time.strftime("%Y-%m-%d"), {})
        day["view"] = day.get("view", 0) + 1
        data["last_view"] = time.time()
        self._save(data)

    def _wait(self, last, span, what):
        gap = random.uniform(span[0], span[1])
        wait = last + gap - time.time()
        if wait > 0:
            log("pacing: %.0fs before the next %s" % (wait, what))
            time.sleep(wait)


# ---------------------------------------------------------------- the tab

class Browser(object):
    """Attach to Chrome on `port`, hold the lock, open one background tab."""

    def __init__(self, port=9224):
        self.port = port
        self._pw = None
        self._locked = False
        self.browser = None
        self.page = None
        self.lock = BrowserLock(port)

    def __enter__(self):
        """RULING R3.1, 2026-09-09. TWO THINGS ABOUT THE ORDER HERE.

        The lock is taken as LATE as it can be: starting Playwright is local work
        that touches no Chrome, so it happens outside the lock and a failure there
        never reaches it. Attaching over CDP is the first step that must be
        exclusive - two Playwright clients on one Chrome block each other's
        navigations - so the lock is taken immediately before that and not before.

        And the whole of the rest is wrapped, catching BaseException so that a
        KeyboardInterrupt counts, because if __enter__ does not RETURN then the
        `with` statement never begins and there is no __exit__ to clean up after
        it. Every fallible step below - the attach, contexts[0], the CDP session,
        the createTarget timeout - used to leave the lock file behind and wedge
        every other session on this machine for fifteen minutes at a time.
        """
        if open_file_dialogs():
            die("a native 'Open' file dialog is already on screen; close it first")
        self._pw = sync_playwright().start()
        try:
            self.lock.__enter__()
            self._locked = True
            try:
                self.browser = self._pw.chromium.connect_over_cdp(
                    "http://localhost:%d" % self.port, timeout=15000)
            except PWError as exc:
                die("no Chrome is listening on port %d (%s). Start the signed-in profile first, "
                    "e.g. bh-profiles.ps1 up cencon" % (self.port, str(exc).splitlines()[0]))
            if not self.browser.contexts:
                die("Chrome on port %d has no browser context to open a tab in" % self.port)
            ctx = self.browser.contexts[0]
            root = self.browser.new_browser_cdp_session()
            with ctx.expect_page(timeout=15000) as opened:
                root.send("Target.createTarget", {"url": "about:blank", "background": True})
            self.page = opened.value
            return self
        except BaseException:
            self._teardown()
            raise

    def __exit__(self, *exc):
        """R3.2 and R3.4. The release sits in the innermost `finally` of
        _teardown, so nothing fallible can come between the last statement and
        it - _pw.stop() raising used to skip the release on the very next line.
        The native-dialog check and its die() run AFTER the lock is already
        gone, never before it."""
        try:
            self._teardown()
        finally:
            spawned = close_file_dialogs("the run")
        if spawned:
            die("a native 'Open' file dialog was spawned during the run; cancelled it")

    def _teardown(self):
        """Close what is open and RELEASE THE LOCK, whatever happens on the way."""
        try:
            try:
                if self.page is not None and not self.page.is_closed():
                    self.page.close()
            finally:
                try:
                    if self.browser is not None:
                        self.browser.close()
                finally:
                    if self._pw is not None:
                        self._pw.stop()
        finally:
            if self._locked:
                self.lock.__exit__(None, None, None)
                self._locked = False

    # -- helpers every verb uses --------------------------------------------

    def goto(self, url, settle=4):
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(settle)
        body = self.page.evaluate("() => document.body ? document.body.innerText.slice(0, 4000) : ''")
        if re.search(r"unusual activity|security verification|let's do a quick security check", body, re.I):
            die("LinkedIn is showing a security check on %s. Stop for today." % url)
        return body

    def assert_signed_in(self, where):
        """A PRESENCE check, run on every read navigation.

        MEASURED 2026-09-09. The obvious test - "the page does not say Sign in" -
        certifies a run that never happened: a profile page can contain those
        words in its own content, and an authwall can be served without them. So
        the test is for something that is only there when we ARE signed in: the
        global navigation's own identity control.

        It cannot be a class name either. On the classic pages
        `.global-nav__me` is present (company about, notifications, Page admin);
        on the new server-driven React pages it does not exist at all (a profile,
        people search, content search all measured 0). What IS on every one of
        them is a button whose accessible name is "Me" or ends in " Me" - on the
        SDUI profile it reads "Me", on the classic company page it reads
        "<the member's name> Me". That is the same control a person clicks, and
        it is what this asserts.
        """
        try:
            n = self.page.get_by_role("button", name=ME_BUTTON).count()
        except PWError as exc:
            die("could not read %s (%s)" % (where, str(exc).splitlines()[0][:120]))
        if n == 0:
            die("not signed in on %s: the global navigation has no identity control. "
                "Sign the cencon Chrome back in - this is NOT an empty result." % where)
        return n

    def read(self, url, where, settle=6):
        """Navigate for a READ: go there, prove we are signed in, prove we landed
        where we asked. Returns the final URL."""
        self.goto(url, settle=settle)
        self.assert_signed_in(where)
        return self.page.url

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
