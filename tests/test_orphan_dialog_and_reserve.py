# -*- coding: utf-8 -*-
"""devthrottle#4901: the two things that made an unattended LinkedIn seat stop
and ask the owner for help.

1. AN ORPHAN NATIVE "Open" DIALOG. Every verb refused while ANY native file
   dialog was on screen, whoever owned it. One left in the shared Chrome
   stopped the Replies round on 2026-11-11 (and a round on 2026-11-05). Now,
   with the browser lock held, a dialog owned by the Chrome we drive is an
   orphan and is cancelled; a dialog owned by anything else still refuses.
   And the working tab intercepts file choosers, so our own clicks cannot put
   one on screen in the first place.

2. THE VIEW RESERVE. Outreach and Replies share 80 views a day; Outreach
   spent all 80 and a new reply waited a day unread. Now a caller that says
   nothing stops at 65, and only a caller that declares a reply read
   (--views-for reply) may use the last 15. The total stays 80.

No browser is opened, no LinkedIn is touched. Win32 is replaced by fakes, except
in the two tests that prove the real ctypes readers against this process.
"""
import contextlib
import io
import os
import socket
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import browser as B
from tests.test_attach import AttachCase, FakePage
from tests.test_pace import PaceCase

CHROME = 4100
CHILD = 4200
OTHER = 7300
_REAL = {n: getattr(B, n) for n in ("open_file_dialogs", "listening_pid", "process_table",
                                     "window_pid", "_wm_close")}


class FakeDesktop(object):
    """The Win32 calls cancel_orphan_dialogs makes, as plain values."""

    def __init__(self, dialogs, listener=CHROME, close_works=True):
        self.dialogs = dict(dialogs)            # hwnd -> owning pid
        self.listener = listener
        self.close_works = close_works
        self.closed = []
        self.table = {CHROME: (1, "chrome.exe"), CHILD: (CHROME, "chrome.exe"),
                      OTHER: (1, "notepad.exe")}

    def install(self, case):
        # Restored to the REAL functions, captured at import: a cleanup runs
        # after tearDown, so restoring whatever a base class had patched in
        # would leave its fake behind for every later test.
        case.addCleanup(lambda: [setattr(B, n, f) for n, f in _REAL.items()])
        B.open_file_dialogs = lambda: list(self.dialogs)
        B.listening_pid = lambda port: self.listener
        B.process_table = lambda: dict(self.table)
        B.window_pid = lambda h: self.dialogs[h]
        B._wm_close = self.close
        return self

    def close(self, h):
        self.closed.append(h)
        if self.close_works:
            self.dialogs.pop(h, None)


def run(fn, *args):
    """(exit code or None, stdout)."""
    out = io.StringIO()
    code = None
    with contextlib.redirect_stdout(out):
        try:
            fn(*args)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue()


# ============================================================ 1. the orphan dialog

class AnOrphanOfOursIsCancelled(unittest.TestCase):

    def test_no_dialog_closes_nothing(self):
        d = FakeDesktop({}).install(self)
        code, _ = run(B.cancel_orphan_dialogs, 9224)
        self.assertIsNone(code)
        self.assertEqual(d.closed, [])

    def test_a_dialog_the_browser_process_owns_is_cancelled_and_logged(self):
        d = FakeDesktop({111: CHROME}).install(self)
        code, out = run(B.cancel_orphan_dialogs, 9224)
        self.assertIsNone(code, out)
        self.assertEqual(d.closed, [111])
        self.assertIn("ORPHAN OPEN DIALOG cancelled (hwnd 111, pid %d)" % CHROME, out)

    def test_a_dialog_a_chrome_child_process_owns_is_cancelled(self):
        d = FakeDesktop({112: CHILD}).install(self)
        code, out = run(B.cancel_orphan_dialogs, 9224)
        self.assertIsNone(code, out)
        self.assertEqual(d.closed, [112])

    def test_a_dialog_that_will_not_close_fails_the_run(self):
        d = FakeDesktop({113: CHROME}, close_works=False).install(self)
        clock = [1000.0]
        saved = B.time.time, B.time.sleep
        self.addCleanup(lambda: (setattr(B.time, "time", saved[0]),
                                 setattr(B.time, "sleep", saved[1])))
        B.time.time = lambda: clock[0]
        B.time.sleep = lambda s: clock.__setitem__(0, clock[0] + s)
        code, out = run(B.cancel_orphan_dialogs, 9224)
        self.assertEqual(code, 1)
        self.assertIn("still on screen", out)


class ADialogOfAnybodyElseStillRefuses(unittest.TestCase):

    def test_another_programs_dialog_refuses_and_is_left_alone(self):
        d = FakeDesktop({221: OTHER}).install(self)
        code, out = run(B.cancel_orphan_dialogs, 9224)
        self.assertEqual(code, 1)
        self.assertEqual(d.closed, [], "a dialog of another program was closed")
        self.assertIn("pid %d notepad.exe" % OTHER, out)
        self.assertIn("not ours to close", out)

    def test_ours_beside_a_foreign_one_closes_neither(self):
        d = FakeDesktop({222: CHROME, 223: OTHER}).install(self)
        code, _ = run(B.cancel_orphan_dialogs, 9224)
        self.assertEqual(code, 1)
        self.assertEqual(d.closed, [])

    def test_no_chrome_on_the_port_means_it_cannot_be_ours(self):
        d = FakeDesktop({224: CHROME}, listener=None).install(self)
        code, out = run(B.cancel_orphan_dialogs, 9224)
        self.assertEqual(code, 1)
        self.assertEqual(d.closed, [])
        self.assertIn("no Chrome listens on port 9224", out)

    def test_a_child_of_a_browser_pid_that_is_not_alive_is_not_ours(self):
        # A stale parent pid: the "child" names CHROME as parent, but CHROME is
        # not in the snapshot, so the pid now listening is some other process.
        d = FakeDesktop({225: CHILD}, listener=CHROME).install(self)
        del d.table[CHROME]
        code, _ = run(B.cancel_orphan_dialogs, 9224)
        self.assertEqual(code, 1)
        self.assertEqual(d.closed, [])

    def test_a_grandchild_is_not_ours(self):
        d = FakeDesktop({226: 9001}).install(self)
        d.table[9001] = (CHILD, "something.exe")
        code, _ = run(B.cancel_orphan_dialogs, 9224)
        self.assertEqual(code, 1)
        self.assertEqual(d.closed, [])


class TheCheckRunsUnderTheLock(AttachCase):
    """Only the lock makes "orphan" true: without it another run of ours could
    be using that very dialog. So the check must run with the lock held, and a
    refusal there must still give the lock back."""

    def test_it_is_called_while_the_lock_is_held(self):
        held_at_call = []
        saved = B.cancel_orphan_dialogs
        self.addCleanup(lambda: setattr(B, "cancel_orphan_dialogs", saved))
        B.cancel_orphan_dialogs = lambda port: held_at_call.append((port, self.held()))
        self.attach()
        br = B.Browser(self.port).__enter__()
        br.__exit__(None, None, None)
        self.assertEqual(held_at_call, [(self.port, True)])

    def test_a_foreign_dialog_refuses_and_releases_the_lock(self):
        FakeDesktop({331: OTHER}).install(self)
        session = self.attach()
        code, out = run(B.Browser(self.port).__enter__)
        self.assertEqual(code, 1)
        self.assertFalse(self.held(), "the refusal left the lock behind")
        self.assertEqual([m for m, _ in session.calls if m == "Target.createTarget"], [],
                         "a tab was opened although the run was refused")

    def test_an_orphan_is_cancelled_and_the_run_goes_on(self):
        d = FakeDesktop({332: CHROME}).install(self)
        self.attach()
        code, out = run(lambda: B.Browser(self.port).__enter__().__exit__(None, None, None))
        self.assertIsNone(code, out)
        self.assertEqual(d.closed, [332])


class ThePostCommandChecksUnderItsLockToo(unittest.TestCase):
    """cc_linkedin.py's post / scheduled / unschedule take the lock in
    connect(); the dialog check must come after it, not before."""

    def test_attach_page_checks_after_connect(self):
        import cc_linkedin as CL
        order = []

        class FakeBrowserObj(object):
            def close(self):
                order.append("browser.close")

        saved = CL.connect, CL.cancel_orphan_dialogs, CL.Page, CL.release
        self.addCleanup(lambda: setattr(CL, "connect", saved[0]) or
                        setattr(CL, "cancel_orphan_dialogs", saved[1]) or
                        setattr(CL, "Page", saved[2]) or setattr(CL, "release", saved[3]))
        CL.connect = lambda p, port: order.append("connect") or FakeBrowserObj()
        CL.cancel_orphan_dialogs = lambda port: order.append("check %d" % port)
        CL.Page = lambda *a: order.append("tab") or "page"
        CL.release = lambda: order.append("release")

        class A(object):
            port, page, page_name = 9224, "1", "X"
        CL.attach_page(None, A(), "shot")
        self.assertEqual(order, ["connect", "check 9224", "tab"])

    def test_a_refusal_there_releases_the_lock(self):
        import cc_linkedin as CL
        order = []

        class FakeBrowserObj(object):
            def close(self):
                order.append("browser.close")

        saved = CL.connect, CL.cancel_orphan_dialogs, CL.release
        self.addCleanup(lambda: setattr(CL, "connect", saved[0]) or
                        setattr(CL, "cancel_orphan_dialogs", saved[1]) or
                        setattr(CL, "release", saved[2]))
        CL.connect = lambda p, port: FakeBrowserObj()
        CL.cancel_orphan_dialogs = lambda port: CL.die("foreign dialog")
        CL.release = lambda: order.append("release")

        class A(object):
            port, page, page_name = 9224, "1", "X"
        code, _ = run(CL.attach_page, None, A(), "shot")
        self.assertEqual(code, 1)
        self.assertEqual(order, ["browser.close", "release"])


class TheTabCannotShowAFileChooser(AttachCase):

    def test_the_working_tab_listens_for_file_choosers(self):
        # Listening is what turns on CDP's Page.setInterceptFileChooserDialog
        # in Playwright: Chrome then reports a chooser instead of showing one.
        self.attach()
        br = B.Browser(self.port).__enter__()
        try:
            self.assertIn("filechooser", br.page.listeners)
        finally:
            br.__exit__(None, None, None)

    def test_an_intercepted_chooser_is_logged_and_does_not_fail(self):
        page = FakePage()
        B.guard_file_chooser(page)
        before = len(B.INTERCEPTED_CHOOSERS)
        code, out = run(page.listeners["filechooser"][0], object())
        self.assertIsNone(code)
        self.assertEqual(len(B.INTERCEPTED_CHOOSERS), before + 1)
        self.assertIn("FILE CHOOSER intercepted", out)


@unittest.skipUnless(sys.platform == "win32", "the Win32 readers")
class TheRealWin32Readers(unittest.TestCase):
    """The ctypes code itself, against this very process - so a wrong struct
    layout or byte order is a red test here, not a refusal on a live seat."""

    def test_listening_pid_finds_this_process_on_a_port_it_listens_on(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        self.addCleanup(s.close)
        self.assertEqual(B.listening_pid(s.getsockname()[1]), os.getpid())

    def test_listening_pid_is_none_on_a_port_nobody_listens_on(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        self.assertIsNone(B.listening_pid(port))

    def test_the_process_table_knows_this_process_and_its_parent(self):
        table = B.process_table()
        self.assertIn(os.getpid(), table)
        self.assertEqual(table[os.getpid()][0], os.getppid())


# ============================================================ 2. the view reserve

class ReserveCase(PaceCase):

    def setUp(self):
        PaceCase.setUp(self)
        B.set_view_purpose("outreach")
        self.addCleanup(B.set_view_purpose, "outreach")

    def take(self, n, purpose):
        B.set_view_purpose(purpose)
        for _ in range(n):
            p = B.Pace()
            p.before_view("a page")
            p.after_view()


class TheLastFifteenAreKeptForReplies(ReserveCase):

    def test_the_numbers(self):
        self.assertEqual(B.Pace.VIEW_CAP, 80, "the total is the owner's 80")
        self.assertEqual(B.Pace.VIEW_CAP - B.Pace.REPLY_RESERVE, 65)

    def test_a_caller_that_says_nothing_stops_at_65(self):
        self.take(65, "outreach")
        code, out = run(B.Pace().before_view, "the 66th")
        self.assertEqual(code, 1)
        self.assertIn("cap 65", out)
        self.assertIn("--views-for reply", out, "the refusal must say how a reply read gets in")
        self.assertEqual(self.counted("view"), 65, "a refused view took a slot")

    def test_a_reply_read_may_use_the_reserve_and_the_total_stays_80(self):
        self.take(65, "outreach")
        self.take(15, "reply")
        self.assertEqual(self.counted("view"), 80)
        code, _ = run(B.Pace().before_view, "the 81st")
        self.assertEqual(code, 1)
        self.assertEqual(self.counted("view"), 80, "the reserve made the day bigger than 80")

    def test_outreach_cannot_eat_reserve_that_replies_left(self):
        # Replies ran first and used 10; outreach still stops at 65 total.
        self.take(10, "reply")
        self.take(55, "outreach")
        code, _ = run(B.Pace().before_view, "one more outreach")
        self.assertEqual(code, 1)
        self.assertEqual(self.counted("view"), 65)

    def test_the_view_cap_precheck_follows_the_purpose(self):
        self.assertEqual(B.Pace().view_cap(), 65)
        B.set_view_purpose("reply")
        self.assertEqual(B.Pace().view_cap(), 80)

    def test_an_unknown_purpose_is_refused_not_guessed(self):
        code, _ = run(B.set_view_purpose, "replies")
        self.assertEqual(code, 1)
        self.assertEqual(B.view_purpose(), "outreach")

    def test_self_views_are_untouched_by_the_reserve(self):
        self.take(65, "outreach")
        p = B.Pace()
        p.before_self_view("our own notifications")      # must not raise
        p.after_view()
        self.assertEqual(self.counted("view_self"), 1)


class EveryVerbTakesViewsFor(unittest.TestCase):

    def _main(self, argv):
        import cc_linkedin as CL
        from cc_linkedin_kit import inbox as I
        seen = []
        saved_fn, saved_argv = I.read_thread, sys.argv
        self.addCleanup(lambda: (setattr(I, "read_thread", saved_fn),
                                 setattr(sys, "argv", saved_argv),
                                 B.set_view_purpose("outreach")))
        I.read_thread = lambda a: seen.append(B.view_purpose())
        sys.argv = ["cc-linkedin"] + argv
        CL.main()
        return seen

    def test_reply_is_set_before_the_verb_runs(self):
        self.assertEqual(self._main(["read-thread", "x", "--views-for", "reply"]), ["reply"])

    def test_the_default_is_outreach(self):
        self.assertEqual(self._main(["read-thread", "x"]), ["outreach"])

    def test_every_subcommand_accepts_it(self):
        import argparse
        import cc_linkedin as CL
        captured = {}
        real = argparse.ArgumentParser.parse_args

        def grab(parser, *a, **kw):
            captured["p"] = parser
            raise SystemExit(0)
        argparse.ArgumentParser.parse_args = grab
        self.addCleanup(setattr, argparse.ArgumentParser, "parse_args", real)
        with self.assertRaises(SystemExit):
            CL.main()
        sub = [a for a in captured["p"]._actions if isinstance(a, argparse._SubParsersAction)][0]
        missing = [n for n, sp in sub.choices.items()
                   if "--views-for" not in sp._option_string_actions]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
