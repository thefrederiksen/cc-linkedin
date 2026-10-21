# -*- coding: utf-8 -*-
"""devthrottle#4340: the working tab opens in a window of its own, and a tab
that cannot be opened is a FAIL line naming the step, never a traceback.

THE DEFECT. `read-profile` died on 2026-10-21 with Playwright's raw
"Timeout 15000ms exceeded while waiting for event 'page'" out of
Browser.__enter__, right after the attach had stopped a service worker. The
service worker was a bystander. Measured the same day on a throwaway Chrome:
a hidden background tab's renderer runs at Windows priority 4 (IDLE), a visible
one at 8, and with every core busy the background tab answered nothing in 25s
on 3 of 3 trials while a tab in a new, never-activated window answered in
0.15-0.24s on 3 of 3. The stall reproduced with no service worker in the
profile at all. The full measurement is in open_working_tab's docstring.

So the tab is created with newWindow AND background, and anything that still
goes wrong on the way to it dies with a line that names the step, closes the
half-open tab, and says the daily view cap was not touched.

THE OPEN QUESTION IN THE ISSUE - did the crashed read count against the 80 a
day? No. read_profile reserves its view as the first statement INSIDE
`with Browser(...)`, and the traceback came out of Browser.__enter__, so that
body never ran. The last test here pins that: a read whose tab never reports in
leaves the counter and the view registry exactly where they were.

No browser is opened here. Playwright is replaced by fakes.
"""
import contextlib
import importlib.util
import io
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import browser as B
from cc_linkedin_kit import people
from tests.test_lock import LockCase

TARGET = "T-4340"


class FakeSession(object):
    """The browser CDP session. Records every call; breakable per method."""

    def __init__(self, fail_on=()):
        self.fail_on = fail_on
        self.calls = []

    def send(self, method, params=None):
        self.calls.append((method, params))
        if method in self.fail_on:
            raise B.PWError("%s refused" % method)
        if method == "Target.createTarget":
            return {"targetId": TARGET}
        if method == "Target.closeTarget":
            return {"success": True}
        return {}


class FakeExpect(object):
    """ctx.expect_page(). With `reports_in` False it times out on the way out
    of the `with`, exactly where Playwright raises it."""

    def __init__(self, reports_in):
        self.reports_in = reports_in
        self.value = FakePage()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *rest):
        if exc_type is None and not self.reports_in:
            raise B.PWTimeout('Timeout 15000ms exceeded while waiting for event "page"')
        return False


class FakePage(object):
    def is_closed(self):
        return False

    def close(self):
        pass


class FakeBrowser(object):
    def __init__(self, session, reports_in=True, session_fails=False):
        self.session = session
        self.reports_in = reports_in
        self.session_fails = session_fails
        self.contexts = [self]          # the browser doubles as its own context

    def new_browser_cdp_session(self):
        if self.session_fails:
            raise B.PWError("Target page, context or browser has been closed")
        return self.session

    def expect_page(self, timeout=None):
        return FakeExpect(self.reports_in)

    def close(self):
        pass


class FakePlaywright(object):
    def __init__(self, browser):
        self.chromium = self
        self.browser = browser

    def connect_over_cdp(self, url, timeout=None):
        return self.browser

    def start(self):
        return self

    def stop(self):
        pass


class AttachCase(LockCase):

    def setUp(self):
        LockCase.setUp(self)
        self._stop_sw = B.Browser._stop_service_workers
        B.Browser._stop_service_workers = lambda self: 0

    def tearDown(self):
        B.Browser._stop_service_workers = self._stop_sw
        LockCase.tearDown(self)

    def attach(self, **kw):
        session = FakeSession(kw.pop("fail_on", ()))
        browser = FakeBrowser(session, **kw)
        B.sync_playwright = lambda: FakePlaywright(browser)
        return session

    def enter_and_die(self, **kw):
        """Enter, expect a die() - SystemExit, NOT a Playwright error - and
        return (the FAIL line, the session's calls)."""
        session = self.attach(**kw)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                B.Browser(self.port).__enter__()
        self.assertFalse(self.held(), "a failed tab open left the lock behind")
        lines = [l for l in out.getvalue().splitlines() if l.startswith("FAIL ")]
        self.assertEqual(len(lines), 1, "expected one FAIL line, got: %r" % out.getvalue())
        return lines[0], session.calls


class TheTabOpensInAWindowOfItsOwn(AttachCase):

    def test_new_window_and_background_both(self):
        # newWindow so the renderer is visible and gets normal priority;
        # background so the window takes no focus. Either one alone is the bug.
        session = self.attach()
        br = B.Browser(self.port).__enter__()
        try:
            created = [p for m, p in session.calls if m == "Target.createTarget"]
            self.assertEqual(created, [{"url": "about:blank", "newWindow": True,
                                        "background": True}])
        finally:
            br.__exit__(None, None, None)


class AFailedOpenIsAFailLine(AttachCase):

    def test_a_tab_that_never_reports_in(self):
        line, calls = self.enter_and_die(reports_in=False)
        self.assertIn("open the working tab", line)
        self.assertIn("did not report in", line)
        self.assertIn(TARGET, line)
        self.assertIn("No view was counted", line)
        # the half-open tab is closed, by its own id, and the line says so
        self.assertIn(("Target.closeTarget", {"targetId": TARGET}), calls)
        self.assertIn("closed again", line)

    def test_a_half_open_tab_that_will_not_close_is_named(self):
        line, _ = self.enter_and_die(reports_in=False, fail_on=("Target.closeTarget",))
        self.assertIn("could NOT be closed", line)
        self.assertIn("No view was counted", line)

    def test_the_cdp_session_failing(self):
        line, calls = self.enter_and_die(session_fails=True)
        self.assertIn("failed at the CDP session", line)
        self.assertIn("returned no tab id", line)
        self.assertIn("No view was counted", line)
        self.assertEqual(calls, [])

    def test_create_target_failing(self):
        line, calls = self.enter_and_die(fail_on=("Target.createTarget",))
        self.assertIn("failed at creating the tab", line)
        self.assertIn("No view was counted", line)
        self.assertNotIn("Target.closeTarget", [m for m, _ in calls])


class TheCrashedReadSpentNoView(AttachCase):
    """The issue's open question, as a test: read-profile on a tab that never
    reports in takes no view - not on the counter, not in the registry."""

    def test_read_profile_on_a_tab_that_never_reports_in(self):
        self.attach(reports_in=False)
        registered = len(B.views_registered())
        a = types.SimpleNamespace(url="someone-else-4340", port=self.port, expect=None)
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                people.read_profile(a)
        self.assertEqual(B.Pace().count("view"), 0)
        self.assertEqual(B.Pace().count("view_self"), 0)
        self.assertEqual(len(B.views_registered()), registered,
                         "a view was registered for a read whose tab never opened")


def _posting_tool():
    """cc_linkedin.py, loaded by path - it is a script, not a package."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "cc_linkedin_under_test", os.path.join(root, "cc_linkedin.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ThePostingPathGivesTheLockBack(AttachCase):
    """The second caller of open_working_tab. connect() takes the lock and the
    Page is built after it; when the tab cannot be opened the die must not
    leave the lock behind. The selftest runs cmd_post IN PROCESS and carries on
    past SystemExit, so a lock left here stalled every later step for 900s."""

    def test_a_tab_that_never_reports_in(self):
        self.attach(reports_in=False)
        fake = B.sync_playwright()
        tool = _posting_tool()
        tool.sync_playwright = lambda: contextlib.nullcontext(fake)
        a = types.SimpleNamespace(port=self.port, page="107519091", page_name="Center Consulting")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                tool.cmd_scheduled(a)
        self.assertIn("FAIL open the working tab", out.getvalue())
        self.assertFalse(self.held(), "the posting path left the browser lock behind")


if __name__ == "__main__":
    unittest.main()
