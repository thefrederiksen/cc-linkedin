# -*- coding: utf-8 -*-
"""R7 to R12: the instrument itself must be able to read low.

From `docs/inspection-slice-2-selftest.md`. The self-test is what every other
claim in this phase is measured with, and the inspection proved six ways it
could not fail when it should. Nothing here opens a browser.
"""
import argparse
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit import selftest as T

GOOD = ("name=A Person; headline=some words; location=Toronto, Ontario, Canada; "
        "company=Acme; degree=2nd; primary=Message; can_connect=yes; connections=418")


class AnEmptyExpectationIsAFailure(unittest.TestCase):
    """R8. `headline=` was accepted as a supplied key, and the headline test is a
    substring test, so "" is in every headline and the sub-check passed for any
    wrong headline at all."""

    def test_a_good_expectation_parses(self):
        got = T._expect(GOOD, "--other-expect")
        self.assertEqual(got["name"], "A Person")
        self.assertEqual(got["connections"], "418")

    def test_an_empty_headline_is_refused(self):
        with self.assertRaises(SystemExit):
            T._expect(GOOD.replace("headline=some words", "headline="), "--other-expect")

    def test_an_empty_name_is_refused(self):
        with self.assertRaises(SystemExit):
            T._expect(GOOD.replace("name=A Person", "name="), "--other-expect")

    def test_an_empty_location_is_refused(self):
        with self.assertRaises(SystemExit):
            T._expect(GOOD.replace("location=Toronto, Ontario, Canada", "location="),
                      "--other-expect")

    def test_an_empty_company_is_refused(self):
        # `company=none` is how a top card stating no employer is written down.
        # An EMPTY company is a person who did not look.
        with self.assertRaises(SystemExit):
            T._expect(GOOD.replace("company=Acme", "company="), "--other-expect")
        self.assertEqual(T._expect(GOOD.replace("company=Acme", "company=none"),
                                   "--other-expect")["company"], "none")

    def test_a_missing_key_is_still_refused(self):
        with self.assertRaises(SystemExit):
            T._expect(GOOD.replace("degree=2nd; ", ""), "--other-expect")

    def test_an_unknown_key_is_still_refused(self):
        with self.assertRaises(SystemExit):
            T._expect(GOOD + "; nickname=Bob", "--other-expect")


class VacuousTruthIsBanned(unittest.TestCase):
    """R11. `all()` over an empty sequence is true, so a row that examined
    nothing reported that everything it examined was fine."""

    def test_a_row_that_checked_nothing_does_not_pass(self):
        self.assertFalse(T.every([]))

    def test_a_row_with_one_good_sub_check_passes(self):
        self.assertTrue(T.every([("something", True, "detail")]))

    def test_a_row_with_a_bad_sub_check_fails(self):
        self.assertFalse(T.every([("something", True, "d"), ("other", False, "d")]))

    def test_all_of_needs_at_least_one_row(self):
        # The shape of P2-8's per-post assertion: every post has an integer
        # impressions count, over zero posts.
        posts = []
        self.assertFalse(T.all_of((isinstance(p, int) for p in posts), len(posts)))
        posts = [1, 2]
        self.assertTrue(T.all_of((isinstance(p, int) for p in posts), len(posts)))
        posts = [1, None]
        self.assertFalse(T.all_of((isinstance(p, int) for p in posts), len(posts)))


class TheRunDeclaresItsRowsAndReconcilesThem(unittest.TestCase):
    """R9. A missing --page silently skipped the whole Page publish-and-delete
    block: not a failed row, no row at all, and no inventory that could name its
    absence. A count of passes means nothing without its denominator."""

    def test_every_declared_row_reporting_once_reconciles(self):
        r = T.Rows()
        r.declare(("A", "B", "C"))
        for name in ("A", "B", "C"):
            r.report(name)
        ok, detail = r.reconcile()
        self.assertTrue(ok, detail)
        self.assertIn("3 rows declared, 3 reported", detail)

    def test_a_row_that_never_ran_fails_the_run_by_name(self):
        r = T.Rows()
        r.declare(("A", "P1-page-post", "C"))
        r.report("A")
        r.report("C")
        ok, detail = r.reconcile()
        self.assertFalse(ok)
        self.assertIn("NEVER RAN", detail)
        self.assertIn("P1-page-post", detail)

    def test_a_row_reported_but_never_declared_fails_too(self):
        r = T.Rows()
        r.declare(("A",))
        r.report("A")
        r.report("SOMETHING-ELSE")
        ok, detail = r.reconcile()
        self.assertFalse(ok)
        self.assertIn("SOMETHING-ELSE", detail)

    def test_discovered_work_is_declared_as_it_is_found(self):
        # The leftover sweep finds however many stale Page posts it finds. Each
        # is declared the moment it is known, so it is still owed a report.
        r = T.Rows()
        r.declare(("A",))
        r.report("A")
        r.also("P1-delete-leftover")
        ok, detail = r.reconcile()
        self.assertFalse(ok, "a discovered row that never reported must fail: " + detail)
        r.report("P1-delete-leftover")
        ok, detail = r.reconcile()
        self.assertTrue(ok, detail)

    def test_the_same_row_twice_is_not_a_substitute_for_two_rows(self):
        r = T.Rows()
        r.declare(("P1-read-comments-1", "P1-read-comments-2"))
        r.report("P1-read-comments-1")
        r.report("P1-read-comments-1")
        ok, detail = r.reconcile()
        self.assertFalse(ok)
        self.assertIn("P1-read-comments-2", detail)

    def test_a_missing_page_fixture_fails_the_run(self):
        # The whole run, exercised at its gate: it exits before any browser.
        a = argparse.Namespace(
            page=None, page_name=None, other_profile="https://www.linkedin.com/in/x/",
            other_expect=GOOD, menu_profile="https://www.linkedin.com/in/y/",
            menu_expect=GOOD.replace("company=Acme", "company=none"), post="x", port=9224)
        with self.assertRaises(SystemExit):
            T.run(a)

    def test_the_declared_inventory_covers_both_phases(self):
        self.assertIn("P1-page-post", T.PHASE1_ROWS)
        self.assertIn("P1-page-delete-post", T.PHASE1_ROWS)
        self.assertIn("P2-9", T.PHASE2_ROWS)
        # Every declared name is distinct except where a row genuinely repeats.
        self.assertEqual(len(set(T.PHASE2_ROWS)), len(T.PHASE2_ROWS))


class TheViewCountHasNoConstantToRetune(unittest.TestCase):
    """R7. EXPECTED_VIEWS was a hand-set number that P2-9 compared the view
    counter against, so retuning it made a view-count failure pass."""

    def test_there_is_no_expected_views_constant(self):
        self.assertFalse(hasattr(T, "EXPECTED_VIEWS"),
                         "EXPECTED_VIEWS is back: a test that chooses its own expected number "
                         "is its own oracle")

    def test_no_module_level_integer_stands_in_for_it(self):
        # The defect is a NUMBER the suite can be edited into agreeing with, so
        # this looks for the shape rather than the name.
        ints = {k: v for k, v in vars(T).items()
                if isinstance(v, int) and not isinstance(v, bool) and not k.startswith("__")}
        self.assertEqual(ints, {}, "module-level integers in the self-test: %r" % ints)


class TheChainedPermalinkMustNameTheRightPost(unittest.TestCase):
    """R2.4. P2-6c asserted that read-post returned a non-empty author, which
    proves the page loaded - never in doubt - and could not tell a permalink
    naming the right post from one naming a stranger's."""

    URN = "urn:li:activity:7000000000000000111"
    ROW = {"author": "A Person",
           "text": "This is the post the search card showed, and it is long enough to compare."}
    GOT = {"urn": URN, "author": "A Person",
           "text": "This is the post the search card showed, and it is long enough to compare. "
                   "And here is the rest of it, which the card had truncated."}

    def _ok(self, row, got, urn=None):
        return all(sub[1] for sub in T._same_post(row, got, urn or self.URN))

    def test_the_right_post_passes(self):
        self.assertTrue(self._ok(self.ROW, self.GOT))

    def test_a_stranger_s_post_fails_on_the_author(self):
        other = dict(self.GOT, author="Somebody Else")
        self.assertFalse(self._ok(self.ROW, other))
        # And this is what the old check asserted, which the wrong post satisfies:
        self.assertTrue(bool(other.get("author")))

    def test_a_stranger_s_post_fails_on_the_text(self):
        other = dict(self.GOT, text="A completely different post about something else entirely.")
        self.assertFalse(self._ok(self.ROW, other))

    def test_a_permalink_naming_another_post_fails(self):
        other = dict(self.GOT, urn="urn:li:activity:7000000000000000222")
        self.assertFalse(self._ok(self.ROW, other))

    def test_a_search_row_with_too_little_text_does_not_pass_by_default(self):
        thin = {"author": "A Person", "text": "Hi"}
        got = dict(self.GOT, text="Hi there")
        self.assertFalse(self._ok(thin, got))

    def test_a_search_row_with_no_author_does_not_pass_by_default(self):
        anon = dict(self.ROW, author="")
        got = dict(self.GOT, author="")
        self.assertFalse(self._ok(anon, got))


class NotificationsIsCheckedForWhatTheVerbDoesNotEnforce(unittest.TestCase):
    """R10. The row repeated conditions `notifications` already enforces before
    returning, so it could only go red if the verb crashed."""

    def rows(self, n=3, **over):
        out = []
        for i in range(1, n + 1):
            r = {"rank": i, "text": "something happened", "actor": "A Person",
                 "url": "https://www.linkedin.com/feed/", "unread": True}
            r.update(over)
            out.append(r)
        return out

    def _ok(self, recs, limit=10):
        return all(sub[1] for sub in T._notification_holds(recs, limit))

    def test_a_well_formed_page_passes(self):
        self.assertTrue(self._ok(self.rows()))

    def test_zero_rows_fails(self):
        self.assertFalse(self._ok([]))

    def test_more_rows_than_the_limit_fails(self):
        self.assertFalse(self._ok(self.rows(11), limit=10))

    def test_ranks_that_repeat_or_skip_fail(self):
        recs = self.rows(3)
        recs[2]["rank"] = 2
        self.assertFalse(self._ok(recs))

    def test_a_row_naming_neither_an_actor_nor_a_target_fails(self):
        recs = self.rows(3)
        recs[1]["actor"] = None
        recs[1]["url"] = None
        self.assertFalse(self._ok(recs))

    def test_unread_that_is_not_a_boolean_fails(self):
        recs = self.rows(3)
        recs[0]["unread"] = "yes"
        self.assertFalse(self._ok(recs))


class ProfileBMustBeTheShapeTheDesignAsksFor(unittest.TestCase):
    """R12. The row accepted 3rd and 3rd+ as well as 1st and 2nd."""

    def test_only_first_and_second_degree(self):
        self.assertEqual(T.PROFILE_B_DEGREES, ("1st", "2nd"))

    def test_third_degree_is_not_accepted(self):
        for degree in ("3rd", "3rd+", "you", None, ""):
            self.assertNotIn((degree or "").lower(), T.PROFILE_B_DEGREES,
                             "%r must not satisfy profile B's required shape" % degree)


if __name__ == "__main__":
    unittest.main()
