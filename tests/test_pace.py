# -*- coding: utf-8 -*-
"""R15: pace.json must not claim a guarantee it cannot keep.

From `docs/inspection-slice-4-claims.md`. `Pace` said its file makes the caps
hold "across sessions and agents". It could not: `before()` loaded and checked,
the action happened, and `after()` separately reloaded and incremented, with no
lock and no atomic write. Two writers at 59 both passed a cap of 60, both acted,
and both saved 60 - so 61 actions happened and the file said 60. Whole fields
overwrote each other the same way, so the spacing timestamps could be lost too.

These run the race for real, with threads. They are not deterministic proofs of
absence - a race that does not show is not a race that cannot happen - so each
one repeats enough to make the old code fail reliably, and the numbers below are
what it took: the lost-update test loses roughly a third of its increments
against the old code on this machine.

No browser, no network.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit import browser as B


class PaceCase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cc-linkedin-pace-")
        self._state = B.STATE_DIR
        B.STATE_DIR = self.dir
        self._gap, self._vgap = B.Pace.GAP, B.Pace.VIEW_GAP
        B.Pace.GAP = (0, 0)
        B.Pace.VIEW_GAP = (0, 0)
        del B._VIEWS[:]

    def tearDown(self):
        B.STATE_DIR = self._state
        B.Pace.GAP, B.Pace.VIEW_GAP = self._gap, self._vgap
        del B._VIEWS[:]
        shutil.rmtree(self.dir, ignore_errors=True)

    def counted(self, kind="view"):
        return B.Pace().count(kind)


class NoIncrementIsLost(PaceCase):
    """The read-modify-write is inside a lock, so concurrent writers do not
    overwrite each other's counts."""

    def test_forty_concurrent_views_count_forty(self):
        n, threads = 40, []
        errors = []

        def one():
            try:
                p = B.Pace()
                p.before_view("a page")
                p.after_view()
            except BaseException as exc:          # a die() would be SystemExit
                errors.append(exc)

        for _ in range(n):
            threads.append(threading.Thread(target=one))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [], "%r" % (errors[:3],))
        self.assertEqual(self.counted("view"), n,
                         "%d of %d views were lost to a read-modify-write race" %
                         (n - self.counted("view"), n))

    def test_the_file_always_parses(self):
        # The atomic replace: no reader can see a half-written pace.json, and no
        # temporary file is left behind.
        p = B.Pace()
        for _ in range(5):
            p.before_view("a page")
            p.after_view()
        with open(p.path, encoding="utf-8") as f:
            json.load(f)
        leftovers = [f for f in os.listdir(self.dir) if f.startswith("pace-")]
        self.assertEqual(leftovers, [], "temporary files left behind: %r" % leftovers)


class TheCapIsAReservation(PaceCase):
    """The cap check and the increment are ONE atomic step, so two runs cannot
    both take the same last slot."""

    def test_the_last_slot_goes_to_exactly_one_of_them(self):
        cap = B.Pace.VIEW_CAP
        p = B.Pace()
        for _ in range(cap - 1):                  # fill it to one below the cap
            p._reserve("view", None, "views")
        self.assertEqual(self.counted("view"), cap - 1)

        got, refused = [], []

        def one():
            try:
                B.Pace().before_view("a page")
                got.append(1)
            except SystemExit:
                refused.append(1)

        threads = [threading.Thread(target=one) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(got), 1,
                         "%d runs were allowed past a cap with one slot left" % len(got))
        self.assertEqual(len(refused), 7)
        self.assertEqual(self.counted("view"), cap,
                         "the counter went past the cap to %d" % self.counted("view"))

    def test_over_the_cap_refuses_without_taking_a_slot(self):
        p = B.Pace()
        for _ in range(B.Pace.VIEW_CAP):
            p._reserve("view", None, "views")
        with self.assertRaises(SystemExit):
            B.Pace().before_view("a page")
        self.assertEqual(self.counted("view"), B.Pace.VIEW_CAP,
                         "a refused view still took a slot")


class TheRegistryFollowsTheCounter(PaceCase):
    """R7's registry and the pacing file are two independent records of the same
    thing, which is the only reason comparing them means anything."""

    def test_a_completed_view_is_registered_and_counted(self):
        p = B.Pace()
        p.before_view("the profile of somebody")
        p.after_view()
        self.assertEqual(len(B.views_taken()), 1)
        self.assertEqual(B.views_taken()[0]["what"], "the profile of somebody")
        self.assertEqual(self.counted("view"), 1)

    def test_a_view_refused_at_the_cap_is_registered_but_not_counted(self):
        p = B.Pace()
        for _ in range(B.Pace.VIEW_CAP):
            p._reserve("view", None, "views")
        with self.assertRaises(SystemExit):
            B.Pace().before_view("one too many")
        self.assertEqual(len(B.views_taken()), 0, "a refused view must not count as taken")
        self.assertEqual(len(B.views_registered()), 1, "it must still be on the record as tried")


if __name__ == "__main__":
    unittest.main()
