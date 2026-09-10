# -*- coding: utf-8 -*-
"""R3: the lock is released on every exit path, and a lock we cannot read is
broken rather than held.

From `docs/inspection-slice-3-verbs.md`, finding 1, CRITICAL. The lock was taken
before several fallible entry operations and only the CDP-connect failure
released it, so a failure in `sync_playwright().start()`, `contexts[0]`, the CDP
session, or the `createTarget` timeout left `__enter__` never returning and the
lock file behind - with no `__exit__` to run, because the `with` statement never
began. On the way out, `_pw.stop()` raising skipped the release on the very next
line. And a half-written lock file parsed as `{}`, had no pid, was never
classified as dead, and so was never reclaimed by anything: every later session
waited fifteen minutes, gave up, and left it there again.

A wedged lock stalls every other session on this machine, including the job that
posts the owner's video series each morning.

No browser is opened here. Playwright is replaced by fakes that fail at each of
the points the inspector named.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit import browser as B


class _Boom(Exception):
    pass


class FakePlaywright(object):
    """A stand-in for sync_playwright().start(), breakable at each entry step."""

    def __init__(self, fail_at=None, fail_stop=False):
        self.fail_at = fail_at
        self.fail_stop = fail_stop
        self.stopped = False
        self.chromium = self

    # -- the entry steps, in the order Browser.__enter__ performs them -------
    def connect_over_cdp(self, url, timeout=None):
        if self.fail_at == "connect":
            raise B.PWError("no browser here")
        return FakeBrowser(self.fail_at)

    def stop(self):
        self.stopped = True
        if self.fail_stop:
            raise _Boom("playwright refused to stop")


class FakeBrowser(object):
    def __init__(self, fail_at):
        self.fail_at = fail_at
        self.closed = False
        self.contexts = [] if fail_at == "contexts" else [FakeContext(fail_at)]

    def new_browser_cdp_session(self):
        if self.fail_at == "cdp-session":
            raise _Boom("no CDP session")
        return FakeCdp(self.fail_at)

    def close(self):
        self.closed = True


class FakeContext(object):
    def __init__(self, fail_at):
        self.fail_at = fail_at

    def expect_page(self, timeout=None):
        return FakeExpect(self.fail_at)


class FakeExpect(object):
    def __init__(self, fail_at):
        self.fail_at = fail_at
        self.value = FakePage()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.fail_at == "createTarget":
            raise B.PWTimeout("no page appeared")
        return False


class FakeCdp(object):
    def __init__(self, fail_at):
        self.fail_at = fail_at

    def send(self, method, params=None):
        return {}


class FakePage(object):
    def __init__(self):
        self.closed = False

    def is_closed(self):
        return self.closed

    def close(self):
        self.closed = True


class LockCase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cc-linkedin-lock-")
        self._state = B.STATE_DIR
        B.STATE_DIR = self.dir
        self._dialogs = B.open_file_dialogs
        self._close = B.close_file_dialogs
        B.open_file_dialogs = lambda: []
        B.close_file_dialogs = lambda where: []
        self._pw = B.sync_playwright
        self.port = 9999
        self.lock_path = os.path.join(self.dir, "browser-%d.lock" % self.port)

    def tearDown(self):
        B.STATE_DIR = self._state
        B.open_file_dialogs = self._dialogs
        B.close_file_dialogs = self._close
        B.sync_playwright = self._pw
        shutil.rmtree(self.dir, ignore_errors=True)

    def _playwright(self, **kw):
        fake = FakePlaywright(**kw)
        B.sync_playwright = lambda: _Starter(fake)
        return fake

    def held(self):
        return os.path.exists(self.lock_path)

    def holder(self):
        with open(self.lock_path, encoding="utf-8") as f:
            return json.load(f)


class _Starter(object):
    def __init__(self, fake):
        self.fake = fake

    def start(self):
        if self.fake.fail_at == "start":
            raise _Boom("playwright would not start")
        return self.fake


class EntryFailuresReleaseTheLock(LockCase):
    """R3.1: ANY exception out of __enter__ releases the lock before it
    propagates - there is no __exit__ to do it, because the with never began."""

    def _enter_and_fail(self, fail_at):
        self._playwright(fail_at=fail_at)
        br = B.Browser(self.port)
        with self.assertRaises(BaseException):
            br.__enter__()
        self.assertFalse(self.held(),
                         "the lock file survived a failure at %r: %s" % (fail_at, self.lock_path))

    def test_playwright_will_not_start(self):
        self._enter_and_fail("start")

    def test_no_chrome_on_the_port(self):
        self._enter_and_fail("connect")

    def test_the_browser_has_no_context(self):
        self._enter_and_fail("contexts")

    def test_the_cdp_session_fails(self):
        self._enter_and_fail("cdp-session")

    def test_create_target_times_out(self):
        self._enter_and_fail("createTarget")

    def test_a_keyboard_interrupt_during_entry(self):
        # BaseException, so a plain `except Exception` would miss it.
        class Interrupting(_Starter):
            def start(self):
                raise KeyboardInterrupt()
        B.sync_playwright = lambda: Interrupting(None)
        br = B.Browser(self.port)
        with self.assertRaises(KeyboardInterrupt):
            br.__enter__()
        self.assertFalse(self.held())

    def test_a_successful_entry_does_hold_the_lock(self):
        # The control. If entry stopped taking the lock at all, every test above
        # would pass for the wrong reason.
        self._playwright()
        br = B.Browser(self.port)
        br.__enter__()
        self.assertTrue(self.held(), "a successful entry must HOLD the lock")
        br.__exit__(None, None, None)
        self.assertFalse(self.held())


class CleanupReleasesTheLock(LockCase):
    """R3.2: released in a finally that nothing can skip. No fallible call may
    sit between the last statement and the release."""

    def test_playwright_stop_raising_does_not_strand_the_lock(self):
        self._playwright(fail_stop=True)
        br = B.Browser(self.port)
        br.__enter__()
        self.assertTrue(self.held())
        try:
            br.__exit__(None, None, None)
        except _Boom:
            pass
        self.assertFalse(self.held(), "_pw.stop() raising skipped the release")

    def test_a_native_dialog_check_cannot_sit_before_the_release(self):
        # R3.4: close_file_dialogs and its die must not sit between the release
        # and the end of __exit__.
        B.close_file_dialogs = lambda where: [1234]
        self._playwright()
        br = B.Browser(self.port)
        br.__enter__()
        with self.assertRaises(SystemExit):
            br.__exit__(None, None, None)
        self.assertFalse(self.held(), "the dialog failure was raised while the lock was held")


class AnUnreadableLockIsBroken(LockCase):
    """R3.3: written atomically, so a half-written lock cannot exist; and once it
    cannot exist, a lock file that will not parse is BROKEN and is reclaimed."""

    def test_an_empty_lock_file_is_reclaimed(self):
        open(self.lock_path, "w").close()
        lock = B.BrowserLock(self.port, wait=5)
        lock.__enter__()                       # must not wait, must not die
        self.assertTrue(self.held())
        self.assertEqual(self.holder()["pid"], os.getpid())
        lock.__exit__(None, None, None)

    def test_a_half_written_lock_file_is_reclaimed(self):
        with open(self.lock_path, "w") as f:
            f.write('{"pid": 12')
        lock = B.BrowserLock(self.port, wait=5)
        lock.__enter__()
        self.assertEqual(self.holder()["pid"], os.getpid())
        lock.__exit__(None, None, None)

    def test_a_lock_with_no_pid_is_reclaimed(self):
        with open(self.lock_path, "w") as f:
            json.dump({"since": "yesterday"}, f)
        lock = B.BrowserLock(self.port, wait=5)
        lock.__enter__()
        self.assertEqual(self.holder()["pid"], os.getpid())
        lock.__exit__(None, None, None)

    def test_a_live_holder_is_still_waited_for(self):
        # The control for the three above: a readable lock held by a LIVE pid is
        # not reclaimable, and the waiter gives up loudly rather than stealing it.
        with open(self.lock_path, "w") as f:
            json.dump({"pid": os.getpid(), "since": "now", "argv": ["selftest"]}, f)
        lock = B.BrowserLock(self.port, wait=0)
        with self.assertRaises(SystemExit):
            lock.__enter__()
        self.assertTrue(self.held(), "a healthy holder's lock was taken from it")

    def test_the_lock_file_is_complete_the_moment_it_appears(self):
        lock = B.BrowserLock(self.port, wait=5)
        lock.__enter__()
        holder = self.holder()
        self.assertEqual(holder["pid"], os.getpid())
        self.assertIn("since", holder)
        lock.__exit__(None, None, None)
        self.assertFalse(self.held())

    def test_no_temporary_files_are_left_behind(self):
        lock = B.BrowserLock(self.port, wait=5)
        lock.__enter__()
        lock.__exit__(None, None, None)
        self.assertEqual(os.listdir(self.dir), [])

# ================================ R3.3 AS AMENDED, 2026-09-10 =================
#
# The original rule was "a lock we cannot READ is broken". It earned that from
# the atomic link-into-place guarantee: a lock file that exists has complete
# bytes, so bytes that do not parse mean a broken record. That argument is about
# CONTENT and it is sound. It says NOTHING about a failure to OPEN the file, and
# the code applied it to both - so on Windows a transient sharing violation
# (delete-pending, someone else mid-release) made a run announce
#
#     lock is BROKEN ... taking it over
#
# and reclaim a lock a LIVE holder was still inside. R15's own forty-thread test
# then lost an increment. Measured on almost every run: see
# docs/evidence/lock-steals-itself-on-windows.txt.
#
# THE AMENDED RULE, the Architect's, 2026-09-10:
#   * "broken" means the file WAS opened and read and its content is not a valid
#     record. That alone is reclaimable, exactly as before.
#   * ANY failure to open is not evidence about the content. Retry a bounded
#     number of times with a short backoff; if it persists, treat the lock as
#     HELD and wait. FAIL CLOSED. Never reclaim on an open failure.
#
# A failure to read is not a reading of failure.


class _Unreadable(object):
    """Makes reading the lock record fail, the way Windows does when the file is
    open elsewhere or has a delete pending on it."""

    def __init__(self, exc, times=None, real=None):
        self.exc, self.times, self.calls = exc, times, 0
        # The REAL reader, captured before the swap. Reaching for
        # B._read_lock_record here would call this object again.
        self.real = real or B._read_lock_record

    def __call__(self, path):
        self.calls += 1
        if self.times is None or self.calls <= self.times:
            raise self.exc
        return self.real(path)


class AnOpenFailureIsNotEvidenceAboutTheContent(LockCase):

    def setUp(self):
        LockCase.setUp(self)
        self._read = B._read_lock_record
        self.logged = []
        self._log = B.log
        B.log = lambda msg: self.logged.append(msg)

    def tearDown(self):
        B._read_lock_record = self._read
        B.log = self._log
        LockCase.tearDown(self)

    def _held_by_a_live_process(self):
        with open(self.lock_path, "w") as f:
            json.dump({"pid": os.getpid(), "since": "now", "argv": ["selftest"]}, f)

    def test_a_lock_that_cannot_be_opened_is_never_reclaimed(self):
        """THE DEFECT, stated as a test. A live holder, and every attempt to read
        who it is answers with a sharing violation."""
        self._held_by_a_live_process()
        mine = self.holder()
        B._read_lock_record = _Unreadable(PermissionError(13, "Access is denied"))
        lock = B.BrowserLock(self.port, wait=0.4)
        lock.poll = 0.02
        with self.assertRaises(SystemExit):
            lock.__enter__()
        self.assertTrue(self.held(), "the lock was taken from a holder we simply could not read")
        self.assertEqual(self.holder(), mine, "the holder's own record was overwritten")

    def test_it_does_not_call_a_healthy_lock_broken(self):
        """The log line is half the defect: 'BROKEN ... taking it over' is
        printed today for a lock that is perfectly fine."""
        self._held_by_a_live_process()
        B._read_lock_record = _Unreadable(PermissionError(13, "Access is denied"))
        lock = B.BrowserLock(self.port, wait=0.4)
        lock.poll = 0.02
        with self.assertRaises(SystemExit):
            lock.__enter__()
        said = " ".join(self.logged).lower()
        self.assertNotIn("broken", said, "an unreadable lock was announced as broken: %s" % said)
        self.assertIn("could not be read", said,
                      "the log does not say which of the two cases it saw: %s" % said)

    def test_a_transient_unreadability_resolves_without_anybody_reclaiming(self):
        """It reads on a later attempt - the ordinary case - and what it finds
        then is a live holder, which is waited for."""
        self._held_by_a_live_process()
        B._read_lock_record = _Unreadable(PermissionError(13, "Access is denied"),
                                          times=2, real=self._read)
        lock = B.BrowserLock(self.port, wait=0.4)
        lock.poll = 0.02
        with self.assertRaises(SystemExit):
            lock.__enter__()
        self.assertTrue(self.held())
        self.assertNotIn("broken", " ".join(self.logged).lower())

    def test_a_lock_that_vanished_is_simply_acquired(self):
        """FileNotFoundError is the holder RELEASING it between our failed link
        and our read. Nothing is broken and nothing is reclaimed - the next link
        attempt just succeeds."""
        self._held_by_a_live_process()

        def vanish(path):
            os.remove(path)
            raise FileNotFoundError(2, "No such file or directory")

        B._read_lock_record = vanish
        lock = B.BrowserLock(self.port, wait=5)
        lock.poll = 0.02
        lock.__enter__()
        self.assertEqual(self.holder()["pid"], os.getpid())
        self.assertNotIn("broken", " ".join(self.logged).lower())
        lock.__exit__(None, None, None)

    def test_content_that_does_not_parse_is_STILL_reclaimed(self):
        """The control. The amendment narrows nothing about content: R3.3's
        original rule stands, and it is what makes a genuinely wedged lock
        recoverable. If this goes red the fix has overshot."""
        with open(self.lock_path, "w") as f:
            f.write('{"pid": 12')
        lock = B.BrowserLock(self.port, wait=5)
        lock.__enter__()
        self.assertEqual(self.holder()["pid"], os.getpid())
        self.assertIn("broken", " ".join(self.logged).lower(),
                      "a genuinely broken record must still say so")
        lock.__exit__(None, None, None)


class TheAcquisitionPathSurvivesEveryOSError(LockCase):
    """os.link's destination can answer with a sharing violation rather than
    FileExistsError while somebody else is mid-release. __enter__ caught only
    FileExistsError, so that escaped to the caller as
    PermissionError(13, 'Access is denied') - which is symptom 2 in the
    evidence file."""

    def setUp(self):
        LockCase.setUp(self)
        self._link = os.link

    def tearDown(self):
        os.link = self._link
        LockCase.tearDown(self)

    def test_a_sharing_violation_on_the_link_does_not_escape(self):
        calls = []

        def flaky(src, dst):
            calls.append(1)
            if len(calls) <= 3:
                raise PermissionError(13, "Access is denied")
            return self._link(src, dst)

        os.link = flaky
        lock = B.BrowserLock(self.port, wait=5)
        lock.poll = 0.02
        lock.__enter__()                       # must not raise PermissionError
        self.assertEqual(self.holder()["pid"], os.getpid())
        lock.__exit__(None, None, None)

    def test_a_link_that_never_works_gives_up_loudly_rather_than_raising_oserror(self):
        os.link = lambda src, dst: (_ for _ in ()).throw(PermissionError(13, "Access is denied"))
        lock = B.BrowserLock(self.port, wait=0.2)
        lock.poll = 0.02
        with self.assertRaises(SystemExit):
            lock.__enter__()


if __name__ == "__main__":
    unittest.main()
