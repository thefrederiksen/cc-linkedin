# -*- coding: utf-8 -*-
"""R7 to R12: the instrument itself must be able to read low.

From `docs/inspection-slice-2-selftest.md`. The self-test is what every other
claim in this phase is measured with, and the inspection proved six ways it
could not fail when it should. Nothing here opens a browser.
"""
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


if __name__ == "__main__":
    unittest.main()
