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


# ============================================================ THE view/view_self SPLIT
#
# docs/ruling-view-cap-2026-09-09.md, implemented 2026-09-10. The safety cap
# exists because high-volume viewing of OTHER PEOPLE'S profiles is what scraping
# looks like from the outside. Loading our own profile is not that: it notifies
# nobody and appears in nobody's "who viewed your profile".
#
# THE WHOLE RISK OF THIS CHANGE, and what these tests are for: a split like this
# is one classification mistake away from becoming a way to spend MORE than 80
# views on strangers. So every test below asks the same question from a
# different side - can anything that is not positively ours reach the uncapped
# counter? The answer has to be no by construction, not by inspection.


class TheSplitIsDecidedByWhoseSurfaceItIs(PaceCase):

    def test_the_owner_is_recognised_however_the_slug_is_written(self):
        for slug in ("sorenfrederiksen", "SorenFrederiksen", "/sorenfrederiksen/",
                     "  sorenfrederiksen  "):
            self.assertTrue(B.is_own_profile(slug), slug)

    def test_a_page_the_owner_administers_is_recognised_by_id_and_by_slug(self):
        self.assertTrue(B.is_own_page("107519091"))
        self.assertTrue(B.is_own_page("centerconsulting-inc"))
        self.assertTrue(B.is_own_page("CenterConsulting-Inc"))

    def test_everything_else_is_somebody_else_including_the_near_misses(self):
        """FAIL CLOSED. The cheap outcome - uncapped - must require a positive
        match, so an empty value, a None, a lookalike and a substring all have
        to come out as somebody else's. A prefix or substring rule here would
        make `sorenfrederiksen-2` free, and a stranger's page id that happens to
        contain ours free with it."""
        for slug in ("", None, "somebodyelse", "sorenfrederiksen-2",
                     "not-sorenfrederiksen", "sorenfrederiksenx", "in"):
            self.assertFalse(B.is_own_profile(slug), repr(slug))
        for key in ("", None, "1075190912", "10751909", "someone-else-inc",
                    "centerconsulting-inc-2", "107519091x"):
            self.assertFalse(B.is_own_page(key), repr(key))


class ASelfViewDoesNotSpendTheSafetyNumber(PaceCase):

    def test_a_self_view_counts_on_its_own_counter_and_not_on_the_capped_one(self):
        p = B.Pace()
        p.before_self_view("the owner's own profile")
        p.after_view()
        self.assertEqual(self.counted("view_self"), 1)
        self.assertEqual(self.counted("view"), 0,
                         "a view of our own profile spent the safety number")

    def test_a_self_view_is_counted_and_reported_not_silently_free(self):
        """The ruling says COUNTED and reported, not capped. A runaway loop on
        our own profile must still be visible in pace.json, so 'uncapped' may
        not be implemented as 'not counted at all'."""
        p = B.Pace()
        for i in range(5):
            p.before_self_view("own profile %d" % i)
            p.after_view()
        self.assertEqual(self.counted("view_self"), 5)
        with open(os.path.join(self.dir, "pace.json"), encoding="utf-8") as f:
            day = json.load(f)[__import__("time").strftime("%Y-%m-%d")]
        self.assertIn("view_self", day, "pace.json does not report self views at all")

    def test_a_self_view_still_works_when_the_safety_cap_is_exhausted(self):
        p = B.Pace()
        for _ in range(B.Pace.VIEW_CAP):
            p._reserve("view", None, "views")
        p.before_self_view("the owner's own profile")   # must not raise
        p.after_view()
        self.assertEqual(self.counted("view_self"), 1)


class TheSplitCannotBeUsedToSPENDMoreOnStrangers(PaceCase):
    """The one failure mode that would make this ruling a mistake."""

    def test_the_eighty_first_view_of_somebody_else_is_still_refused(self):
        p = B.Pace()
        for _ in range(50):
            p.before_self_view("own profile")
            p.after_view()
        for _ in range(B.Pace.VIEW_CAP):
            p._reserve("view", None, "views")
        with self.assertRaises(SystemExit):
            B.Pace().before_view("one stranger too many")
        self.assertEqual(self.counted("view"), B.Pace.VIEW_CAP)

    def test_the_capped_counter_is_the_one_the_cap_is_read_from(self):
        """If the cap were read from the SUM, self views would eat the safety
        number; if the self counter were capped, the ruling would not have
        happened. Both counters are asserted, separately, on purpose."""
        p = B.Pace()
        p.before_view("somebody else")
        p.after_view()
        p.before_self_view("ourselves")
        p.after_view()
        self.assertEqual((self.counted("view"), self.counted("view_self")), (1, 1))


class TheRegistryLearnedTheDistinction(PaceCase):
    """R7's registry is one half of P2-9's comparison. After the split there are
    two counters, so a registry that cannot say which one a view belongs to
    makes P2-9 unreconcilable - and the answer to that is to teach the registry,
    never to loosen the row."""

    def test_every_registered_view_says_which_counter_it_is_on(self):
        p = B.Pace()
        p.before_view("somebody else")
        p.after_view()
        p.before_self_view("ourselves")
        p.after_view()
        kinds = [v["kind"] for v in B.views_taken()]
        self.assertEqual(kinds, ["view", "view_self"])

    def test_the_registry_can_be_read_one_counter_at_a_time(self):
        p = B.Pace()
        p.before_view("stranger one")
        p.after_view()
        p.before_self_view("ourselves")
        p.after_view()
        p.before_view("stranger two")
        p.after_view()
        self.assertEqual([v["what"] for v in B.views_taken("view")],
                         ["stranger one", "stranger two"])
        self.assertEqual([v["what"] for v in B.views_taken("view_self")], ["ourselves"])
        self.assertEqual(len(B.views_taken()), 3, "unfiltered must still be everything")

    def test_each_registry_half_matches_its_own_counter(self):
        """This is P2-9's assertion, in miniature and offline: the pacing file's
        delta for each counter equals what the registry recorded for it."""
        p = B.Pace()
        before = (self.counted("view"), self.counted("view_self"))
        for _ in range(3):
            p.before_view("a stranger")
            p.after_view()
        for _ in range(2):
            p.before_self_view("ourselves")
            p.after_view()
        after = (self.counted("view"), self.counted("view_self"))
        self.assertEqual(after[0] - before[0], len(B.views_taken("view")))
        self.assertEqual(after[1] - before[1], len(B.views_taken("view_self")))


class ARefusedSelfViewIsImpossibleButStillOnTheRecord(PaceCase):

    def test_a_self_view_is_registered_before_it_is_reserved(self):
        """Same shape as the capped path: the registry records the ATTEMPT, and
        `counted` is what separates a view that happened from one that did not."""
        p = B.Pace()
        p.before_self_view("ourselves")
        self.assertEqual(len(B.views_registered()), 1)
        self.assertEqual(B.views_registered()[0]["kind"], "view_self")
        self.assertTrue(B.views_registered()[0]["counted"])


if __name__ == "__main__":
    unittest.main()
