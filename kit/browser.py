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

class FileLock(object):
    """Mutual exclusion around one file, held by a sentinel beside it.

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

    def __init__(self, path, wait=900, what="the browser"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self.wait = wait
        self.what = what

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

    # Seconds between attempts while somebody else holds it. Short by default:
    # this class guards a state file whose critical section is a read, an
    # increment and a write. The browser lock overrides it - waiting three
    # seconds between attempts is right when the holder is a whole run.
    poll = 0.05

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
                        log("waiting for %s: another run holds it (pid %s since %s, %s)"
                            % (self.what, pid, holder.get("since"),
                               " ".join(holder.get("argv", []))))
                        told = True
                    if time.time() > deadline:
                        die("gave up waiting for %s after %ds; pid %s still holds it"
                            % (self.what, self.wait, pid))
                    time.sleep(self.poll)
        finally:
            _discard(tmp)

    def __exit__(self, *exc):
        _discard(self.path)


class BrowserLock(FileLock):
    """One run per Chrome. A second run waits (up to `wait` seconds) and says so.

    Two Playwright clients attached to one Chrome block each other's navigations
    (measured 2026-09-09 14:34), so one Chrome is one run at a time.
    """

    poll = 3

    def __init__(self, port, wait=900):
        FileLock.__init__(self, os.path.join(STATE_DIR, "browser-%d.lock" % port),
                          wait=wait, what="the browser")


def _discard(path, tries=60, gap=0.05):
    """Remove a file this process owns, and say so if it cannot.

    MEASURED 2026-09-09, by the concurrency test written for ruling R15, against
    the R3 fix itself. On Windows, Python's open() does not ask for
    FILE_SHARE_DELETE, so while ANY reader has the lock file open - and every
    waiter reads it to see who holds it - os.remove raises a sharing violation.
    The code here swallowed that as `except OSError: pass`, so a release could
    silently not happen and the lock stayed behind with a live pid in it, which
    no reclaim rule will ever touch. Six concurrent writers wedged permanently
    on the first attempt.

    That is the R3 defect exactly, reintroduced one layer down by an error
    handler that treated "I could not do it" as "it is done". So this RETRIES,
    for a bounded three seconds, and returns False and logs if it still cannot -
    because a lock that will not release is the thing most worth being loud
    about in this file.
    """
    for i in range(tries):
        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            return True
        except OSError as exc:
            if i == tries - 1:
                log("COULD NOT REMOVE %s after %.0fs (%s). If that is a lock file, the next "
                    "run will wait behind it." % (path, tries * gap,
                                                  str(exc).splitlines()[0][:80]))
                return False
            time.sleep(gap)


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

    WHAT THIS FILE ACTUALLY GUARANTEES, AND WHAT IT DOES NOT - ruling R15,
    2026-09-09. This docstring used to say the caps hold "across sessions and
    agents", and the code could not keep that promise: `before` loaded and
    checked, the action happened, and `after` separately reloaded and
    incremented, with no lock and no atomic write. Two runs at 59 both passed a
    cap of 60, both acted, and both saved 60 - so 61 actions happened and the
    file said 60. Whole fields overwrote each other the same way, so the spacing
    timestamps could be lost too.

    IT NOW GUARANTEES, across processes on this machine:
      * the cap check and the increment are ONE atomic critical section, guarded
        by a lock file beside pace.json, so the count is a RESERVATION. Two runs
        cannot both take the same last slot.
      * every read-modify-write of the file happens inside that lock and the file
        is replaced atomically, so no increment and no timestamp is lost.

    IT DOES NOT GUARANTEE:
      * that a reserved action happened. The slot is taken immediately before the
        action, so an action that then fails is still counted. That is the
        conservative direction on purpose: this cap exists to keep the owner's
        account safe, and a request that errored may still have reached LinkedIn.
      * anything about another machine. The file is local.

    An overstated guarantee in the one file that exists to keep his account safe
    is worse than an honest limitation, because it is the sentence somebody
    relies on instead of checking.
    """

    CAPS = {"comment": 60, "react": 100, "connect": 20, "message": 30, "invite": 5}
    GAP = (45, 90)         # seconds between outbound actions
    VIEW_CAP = 80          # profile/company/search pages opened per day
    VIEW_GAP = (3, 8)      # seconds between reads

    def __init__(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.path = os.path.join(STATE_DIR, "pace.json")

    def _lock(self):
        """Held for one read-modify-write of pace.json and no longer. Short by
        design: a run must never wait behind another run's 90-second gap."""
        return FileLock(self.path + ".lock", wait=60, what="the pacing file")

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data):
        """Replace pace.json atomically. Only ever called holding the lock."""
        today = time.strftime("%Y-%m-%d")
        for k in [k for k in data if DAY_KEY.match(k) and k < today]:
            del data[k]
        fd, tmp = tempfile.mkstemp(prefix="pace-", dir=STATE_DIR)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1)
            os.replace(tmp, self.path)
        except BaseException:
            _discard(tmp)
            raise

    def _reserve(self, kind, cap, what):
        """Check the cap and take a slot, as ONE atomic step. Returns the count
        after the reservation; dies over the cap without taking one."""
        with self._lock():
            data = self._load()
            day = data.setdefault(time.strftime("%Y-%m-%d"), {})
            n = day.get(kind, 0)
            if cap is not None and n >= cap:
                die("daily cap reached for %s (%d today, cap %d). Tomorrow." % (what, n, cap))
            day[kind] = n + 1
            self._save(data)
            return n + 1

    def _stamp(self, field):
        with self._lock():
            data = self._load()
            data[field] = time.time()
            self._save(data)

    def count(self, kind, when=None):
        """How many of `kind` have been done today. Used by the selftest to prove
        the view counter moved by exactly the number of views the run took."""
        day = self._load().get(when or time.strftime("%Y-%m-%d"), {})
        return day.get(kind, 0)

    # -- outbound -----------------------------------------------------------

    def before(self, kind):
        """Wait out the gap, then RESERVE a slot. Call right before the action.

        The wait comes first and the reservation second, so the window between
        deciding and counting is one atomic step rather than the length of a
        90-second gap (ruling R15).
        """
        self._wait(self._load().get("last_outbound", 0), self.GAP, kind)
        self._reserve(kind, self.CAPS.get(kind), kind)

    def after(self, kind):
        """The action is done. The slot was taken in before(); this records when,
        so the next run spaces itself from it."""
        self._stamp("last_outbound")

    # -- views --------------------------------------------------------------

    def before_view(self, what="page"):
        """One view = one profile, one company page, or one page of search
        results. Refuses over the daily cap; never touches the outbound clock.

        Every view REGISTERS ITSELF here, by name - ruling R7, 2026-09-09. The
        selftest used to compare the day's view counter against EXPECTED_VIEWS,
        a hand-set constant, which made the test its own oracle: retuning the
        constant made a view-count failure pass, and nothing executable derived
        the number independently. The constant is gone. What the run believes it
        viewed is this list; what the pacing file recorded is the counter; and
        they are compared to each other. A disagreement means either the pacing
        is wrong or the registry is, and both deserve a red run.
        """
        _VIEWS.append({"what": what, "counted": False})
        self._wait(self._load().get("last_view", 0), self.VIEW_GAP, "view of %s" % what)
        self._reserve("view", self.VIEW_CAP, "views")
        if _VIEWS:
            _VIEWS[-1]["counted"] = True

    def after_view(self):
        """The page is open. The view was counted in before_view(); this records
        when, so the next read spaces itself from it."""
        self._stamp("last_view")

    def _wait(self, last, span, what):
        gap = random.uniform(span[0], span[1])
        wait = last + gap - time.time()
        if wait > 0:
            log("pacing: %.0fs before the next %s" % (wait, what))
            time.sleep(wait)


# ---------------------------------------------------------------- what we viewed

# This process's own record of every view it took, in order. Appended to by
# Pace.before_view and marked counted by Pace.after_view. It is deliberately
# process-level rather than per-Pace: a run makes several Pace objects and the
# question "what did this run view" is about the run.
_VIEWS = []


def views_taken():
    """The views this process registered and completed, in order."""
    return [v for v in _VIEWS if v["counted"]]


def views_registered():
    """Every view this process began, completed or not."""
    return list(_VIEWS)


def open_tabs(port):
    """The URLs of the pages this Chrome has open.

    Read from the DevTools endpoint over localhost - NOT by attaching a second
    Playwright client, which is the very thing the browser lock exists to
    prevent, and NOT by opening a tab of our own to count tabs with. Raises if
    it cannot read; a tab census that cannot be taken is a broken instrument and
    the caller must fail on it rather than report a tidy zero.
    """
    import urllib.request
    with urllib.request.urlopen("http://localhost:%d/json/list" % port, timeout=8) as r:
        targets = json.loads(r.read().decode("utf-8"))
    return [t.get("url", "") for t in targets if t.get("type") == "page"]


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
