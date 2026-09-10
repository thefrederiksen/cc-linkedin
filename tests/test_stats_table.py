# -*- coding: utf-8 -*-
"""R4: an unreadable table is a failure, and stats must prove which Page it read.

From `docs/inspection-slice-3-verbs.md`, finding 2 and finding 4.

The header assertion in `stats` is sound and the member-analytics trap is
genuinely blocked - the inspector confirmed the header and the cells come from
the same local `table` object. What the header assertion proves is that the
SCHEMA is the one this was written against. It proves nothing about whether a
single number is present, and three shapes went straight through it:

  * the tbody empty after the range refresh - successful exit, `posts: []`,
    `RESULT ... impressions=0`;
  * every row short while the renderer hydrates - all silently discarded with
    `continue`, same successful zero;
  * a cell reading "-" - `(None or 0)` contributing a literal zero to an
    aggregate that then looks like a measurement.

And finding 4: the only final-URL check was for the generic `/admin/analytics`
path, so a bad or unauthorised `--page A` redirected to another administered
Page produced B's numbers labelled as A - precise, plausible, wrong, every run.

No browser here: these are the pure functions the verb reads its table through.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import account as A
from cc_linkedin_kit.people import to_int

HEADER = ["Post title", "Impressions", "Reactions", "Comments", "Reposts"]
COLS = ("Impressions", "Reactions", "Comments", "Reposts")


class TheLandedPageMustBeTheOneAskedFor(unittest.TestCase):

    def test_the_page_id_is_read_out_of_the_url(self):
        self.assertEqual(
            A.page_key("https://www.linkedin.com/company/107519091/admin/analytics/updates/"),
            "107519091")

    def test_a_slug_works_the_same_way(self):
        self.assertEqual(
            A.page_key("https://www.linkedin.com/company/centerconsulting-inc/admin/analytics/"),
            "centerconsulting-inc")

    def test_a_redirect_to_another_page_is_visible(self):
        wanted = "107519091"
        landed = A.page_key("https://www.linkedin.com/company/999999/admin/analytics/updates/")
        self.assertNotEqual(landed, wanted)
        # And the check the verb used to make - the generic path - passes on it,
        # which is the whole finding.
        self.assertIn("/admin/analytics",
                      "https://www.linkedin.com/company/999999/admin/analytics/updates/")

    def test_a_url_with_no_company_segment_reads_as_nothing(self):
        self.assertIsNone(A.page_key("https://www.linkedin.com/feed/"))
        self.assertIsNone(A.page_key(""))
        self.assertIsNone(A.page_key(None))


class AnUnreadableRowIsAFailure(unittest.TestCase):

    def test_a_full_table_reads(self):
        rows = [["A post", "48", "3", "1", "0"], ["Another", "12", "0", "0", "0"]]
        posts = A.rows_to_posts(HEADER, rows, COLS, to_int)
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0]["impressions"], 48)
        self.assertEqual(posts[0]["impressions_raw"], "48")

    def test_one_short_row_fails_instead_of_being_skipped(self):
        rows = [["A post", "48", "3", "1", "0"], ["Another", "12"]]
        with self.assertRaises(SystemExit):
            A.rows_to_posts(HEADER, rows, COLS, to_int)

    def test_every_row_short_fails_rather_than_producing_no_posts(self):
        # The hydration case: the old code discarded all of them with `continue`
        # and returned an empty list, which read as a Page with nothing on it.
        rows = [["A post"], ["Another"]]
        with self.assertRaises(SystemExit):
            A.rows_to_posts(HEADER, rows, COLS, to_int)

    def test_a_dash_cell_becomes_a_null_not_a_zero(self):
        rows = [["A post", "-", "3", "1", "0"]]
        posts = A.rows_to_posts(HEADER, rows, COLS, to_int)
        self.assertIsNone(posts[0]["impressions"])
        self.assertEqual(posts[0]["impressions_raw"], "-")

    def test_a_cell_that_is_not_a_number_still_fails_loudly(self):
        rows = [["A post", "lots", "3", "1", "0"]]
        with self.assertRaises(SystemExit):
            A.rows_to_posts(HEADER, rows, COLS, to_int)


class ASumDoesNotManufactureZeroes(unittest.TestCase):

    def test_a_normal_sum(self):
        posts = A.rows_to_posts(HEADER, [["A", "48", "3", "1", "0"],
                                         ["B", "12", "0", "0", "0"]], COLS, to_int)
        sums = A.sum_of_posts(posts, COLS, A.SUM_SOURCE)
        self.assertEqual(sums["impressions"]["value"], 60)
        self.assertEqual(sums["impressions"]["posts_counted"], 2)
        self.assertEqual(sums["impressions"]["posts_without_a_number"], 0)

    def test_a_post_with_no_number_is_counted_not_zeroed(self):
        posts = A.rows_to_posts(HEADER, [["A", "48", "3", "1", "0"],
                                         ["B", "-", "0", "0", "0"]], COLS, to_int)
        sums = A.sum_of_posts(posts, COLS, A.SUM_SOURCE)
        self.assertEqual(sums["impressions"]["value"], 48)
        self.assertEqual(sums["impressions"]["posts_counted"], 1)
        self.assertEqual(sums["impressions"]["posts_without_a_number"], 1,
                         "a post the sum could not add must be reported, not absorbed")

    def test_no_post_stating_a_number_is_null_with_a_reason_not_zero(self):
        posts = A.rows_to_posts(HEADER, [["A", "-", "-", "-", "-"]], COLS, to_int)
        sums = A.sum_of_posts(posts, COLS, A.SUM_SOURCE)
        self.assertIsNone(sums["impressions"]["value"],
                          "an aggregate with nothing to add must not read as zero")
        self.assertTrue(sums["impressions"]["reason"])

    def test_no_posts_at_all_produces_no_aggregate_to_misread(self):
        self.assertEqual(A.sum_of_posts([], COLS, A.SUM_SOURCE), {})


if __name__ == "__main__":
    unittest.main()
