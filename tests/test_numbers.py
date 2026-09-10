# -*- coding: utf-8 -*-
"""R6: reject the ambiguous, do not normalise it away.

From `docs/inspection-slice-3-verbs.md`, finding 7. `to_int` stripped every
comma and every plus before deciding what the number meant, so the European
`1,2K` became `12K` and returned 12000 instead of 1200 - wrong by a factor of
ten, silently, in a field a caller writes straight into a CRM. Global
plus-stripping turned `12+3` into `123`.

Stripping separators before parsing is the bug. The fix is a grammar.

MEASURED? NO - AND THAT DECIDES ONE CASE. R6.1 leaves it to the Manager whether
a comma followed by one or two digits is accepted as a decimal comma or fails,
"after measuring what LinkedIn actually renders in a European locale". That
measurement needs the live site in another locale and could not be made: the
daily view cap was exhausted. So it FAILS, loudly, which is R6.3's default and
the only safe direction - accepting it would mean guessing between 1200 and 12
with no evidence, and the wrong guess is silent and off by ten. Every English
label this toolkit asserts on ("Me", "More", "About this member", "Content
engagement") says the rendering it reads is the English one, where this form
should not occur at all; if it ever does, a person now finds out.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit import people as P


class NumbersThatParse(unittest.TestCase):

    def check(self, raw, want):
        self.assertEqual(P.to_int(raw, "a count"), want, "%r" % raw)

    def test_plain_integers(self):
        self.check("0", 0)
        self.check("7", 7)
        self.check("500", 500)

    def test_thousands_separators(self):
        self.check("1,234", 1234)
        self.check("12,345", 12345)
        self.check("1,234,567", 1234567)

    def test_abbreviations(self):
        self.check("1.2K", 1200)
        self.check("12.5K", 12500)
        self.check("1.2M", 1200000)
        self.check("3B", 3000000000)
        self.check("1.2k", 1200)

    def test_a_trailing_plus_is_a_lower_bound_marker(self):
        self.check("500+", 500)
        self.check("1,234+", 1234)
        self.check("1.2K+", 1200)

    def test_surrounding_space(self):
        self.check("  1,234  ", 1234)
        self.check("1.2 K", 1200)


class NumbersThatMustFail(unittest.TestCase):
    """Every ambiguous form fails loudly. A wrong number that looks right is
    worse than no number, because nothing downstream can catch it."""

    def bad(self, raw):
        with self.assertRaises(SystemExit, msg="%r was accepted" % raw):
            P.to_int(raw, "a count")

    def test_the_european_decimal_comma(self):
        # THE FINDING. replace(",", "") turned this into 12K -> 12000, ten times
        # the 1200 it means.
        self.bad("1,2K")
        self.bad("1,2M")
        self.bad("1,23")

    def test_a_comma_that_is_not_a_thousands_group(self):
        self.bad("1,23")
        self.bad("1,2345")
        self.bad("12,34")
        self.bad(",123")
        self.bad("1,")

    def test_a_plus_that_is_not_trailing(self):
        # replace("+", "") turned this into 123.
        self.bad("12+3")
        self.bad("+12")
        self.bad("1+2+3")

    def test_a_bare_decimal_with_no_multiplier(self):
        # "1.234" is 1234 in a European rendering and 1.234 in an English one,
        # and nothing on the page says which. A decimal point is only a decimal
        # point when a K, M or B follows it.
        self.bad("1.234")
        self.bad("1.2")
        self.bad("0.5")

    def test_things_that_are_not_numbers(self):
        self.bad("")
        self.bad("   ")
        self.bad("many")
        self.bad("500 connections")
        self.bad("1 234")                      # a space-separated group
        self.bad(u"1 234")                # the same with a non-breaking space
        self.bad("12,,345")
        self.bad("1.2.3")
        self.bad("K")
        self.bad("1.2KK")

    def test_nothing_at_all_is_a_failure_not_a_null(self):
        self.bad(None)

    def test_a_failure_names_what_it_read(self):
        try:
            P.to_int("1,2K", "the connections count")
        except SystemExit:
            pass
        else:
            self.fail("1,2K was accepted")


if __name__ == "__main__":
    unittest.main()
