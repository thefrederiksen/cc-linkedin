# -*- coding: utf-8 -*-
"""R1 and R2: the post a permalink names must be the post the page says it is.

Every input below came out of `docs/inspection-slice-1-urn.md`. The two the
inspector built by hand - a full urn in a query parameter, and a kind-plus-digits
motif earlier in the slug than the real terminal one - are the reason this whole
pass exists: each produces a WELL-FORMED PERMALINK FOR A DIFFERENT POST, with a
null resolve_error, counted as resolved, indistinguishable from a good row by any
caller. That value then reaches `comment`, `react` and `delete-post`.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit import identity as I

# The post the URL is about, in both hand-built cases below.
#
# THE IDS HERE ARE FABRICATED, deliberately. The inspection's own write-up used
# three ids measured off real cards; this repository is PUBLIC and a post id is a
# stable lookup key to a real person's post, so nothing here reuses them (ruling
# R13). The defect is about the SHAPE of the string, and a made-up id has the
# same shape.
REAL = "urn:li:share:7000000000000000111"
# The other post, whose id is loose in the string where the parser can find it.
OTHER = "urn:li:activity:7000000000000000222"


class ResolveFromTheLandedPage(unittest.TestCase):
    """R1: read the identity off the page; the URL only ever gets to AGREE."""

    def test_a_urn_in_a_query_parameter_does_not_beat_the_page(self):
        # inspection-slice-1, "Concrete breaking input 1".
        dest = ("https://www.linkedin.com/posts/example_topic-share-7000000000000000111"
                "-987654321?quoted=" + OTHER)
        urn, err = I.resolve_post_identity(dest, [REAL])
        self.assertIsNone(err, err)
        self.assertEqual(urn, REAL)

    def test_an_earlier_motif_in_the_slug_does_not_beat_the_page(self):
        # inspection-slice-1, "Concrete breaking input 2".
        dest = ("https://www.linkedin.com/posts/example-activity-7000000000000000222"
                "_topic-share-7000000000000000111-987654321")
        urn, err = I.resolve_post_identity(dest, [REAL])
        self.assertIsNone(err, err)
        self.assertEqual(urn, REAL)

    def test_a_page_that_states_no_identity_is_not_resolved(self):
        dest = "https://www.linkedin.com/posts/example_topic-share-7000000000000000111-987654321"
        urn, err = I.resolve_post_identity(dest, [])
        self.assertIsNone(urn)
        self.assertIn("stated no identity", err)

    def test_the_page_and_the_path_must_agree(self):
        # R1.2: disagreement is a FAIL for the row, never a preference.
        dest = "https://www.linkedin.com/posts/example_topic-share-222222222222222222-987654321"
        urn, err = I.resolve_post_identity(dest, [OTHER])
        self.assertIsNone(urn)
        self.assertIn("urn:li:share:222222222222222222", err)
        self.assertIn(OTHER, err)

    def test_two_stated_identities_are_ambiguity_not_a_first_match(self):
        # R1.3: more than one distinct candidate anywhere is ambiguity.
        dest = "https://www.linkedin.com/feed/update/%s/" % REAL
        urn, err = I.resolve_post_identity(dest, [REAL, OTHER])
        self.assertIsNone(urn)
        self.assertIn(REAL, err)
        self.assertIn(OTHER, err)

    def test_another_host_resolves_to_nothing(self):
        # R1.4. The extractor was a whole-string pattern recogniser, not a
        # LinkedIn post-permalink parser.
        urn, err = I.resolve_post_identity("https://example.invalid/x-share-123456789/", [])
        self.assertIsNone(urn)

    def test_a_company_path_resolves_to_nothing(self):
        urn, err = I.resolve_post_identity(
            "https://www.linkedin.com/company/acme-activity-123456789/", [])
        self.assertIsNone(urn)

    def test_a_school_path_resolves_to_nothing(self):
        urn, err = I.resolve_post_identity(
            "https://www.linkedin.com/school/acme-activity-123456789/", [])
        self.assertIsNone(urn)

    def test_digits_that_do_not_end_the_id_segment_are_not_an_id(self):
        # "even -share-123abc is accepted as share 123" - inspection-slice-1.
        urn, err = I.resolve_post_identity(
            "https://www.linkedin.com/posts/example-share-123abc", [])
        self.assertIsNone(urn)

    def test_a_clean_post_url_agreeing_with_the_page_resolves(self):
        dest = ("https://www.linkedin.com/posts/somebody_some-words-share-7000000000000000333"
                "-AbCd?utm_source=share")
        urn, err = I.resolve_post_identity(dest, ["urn:li:share:7000000000000000333"])
        self.assertIsNone(err, err)
        self.assertEqual(urn, "urn:li:share:7000000000000000333")

    def test_a_feed_update_url_agreeing_with_the_page_resolves(self):
        dest = "https://www.linkedin.com/feed/update/%s/" % REAL
        urn, err = I.resolve_post_identity(dest, [REAL])
        self.assertIsNone(err, err)
        self.assertEqual(urn, REAL)

    def test_a_login_wall_carrying_the_post_in_its_query_resolves_to_nothing(self):
        dest = ("https://www.linkedin.com/uas/login?session_redirect="
                "%2Fposts%2Fexample-share-7000000000000000111-abcd")
        urn, err = I.resolve_post_identity(dest, [])
        self.assertIsNone(urn)


class UrnOfIsAnchoredAndSingular(unittest.TestCase):
    """R2.1: the string handed to a mutating verb must name exactly one post."""

    def _urn_of(self, url):
        def die(msg):
            raise SystemExit(msg)
        return I.urn_of(url, die)

    def test_a_bare_urn_is_accepted(self):
        self.assertEqual(self._urn_of(REAL), REAL)

    def test_a_permalink_is_accepted(self):
        self.assertEqual(self._urn_of("https://www.linkedin.com/feed/update/%s/" % REAL), REAL)

    def test_two_different_urns_in_one_input_is_a_failure(self):
        with self.assertRaises(SystemExit):
            self._urn_of("https://www.linkedin.com/feed/update/%s/?quoted=%s" % (REAL, OTHER))

    def test_the_same_urn_twice_is_not_ambiguous(self):
        self.assertEqual(
            self._urn_of("https://www.linkedin.com/feed/update/%s/?x=%s" % (REAL, REAL)), REAL)

    def test_a_urn_on_another_host_is_a_failure(self):
        with self.assertRaises(SystemExit):
            self._urn_of("https://evil.example/feed/update/%s/" % REAL)

    def test_a_urn_loose_in_a_query_parameter_is_a_failure(self):
        with self.assertRaises(SystemExit):
            self._urn_of("https://www.linkedin.com/search/results/content/?keywords=%s" % REAL)

    def test_a_string_with_no_urn_is_a_failure(self):
        with self.assertRaises(SystemExit):
            self._urn_of("https://www.linkedin.com/in/somebody/")


class TheAnyCardFallbackIsGated(unittest.TestCase):
    """R2.2: `card_any` is allowed ONLY when the page holds exactly one post card
    AND the page's own stated identity is the urn we asked for."""

    WANT = REAL

    def test_one_card_and_the_page_says_it_is_ours(self):
        self.assertTrue(I.may_use_any_card(1, [self.WANT], self.WANT))

    def test_one_card_but_the_page_names_a_different_post(self):
        self.assertFalse(I.may_use_any_card(1, [OTHER], self.WANT))

    def test_one_card_and_the_page_states_nothing(self):
        self.assertFalse(I.may_use_any_card(1, [], self.WANT))

    def test_several_cards_is_never_a_fallback(self):
        self.assertFalse(I.may_use_any_card(4, [self.WANT], self.WANT))

    def test_no_cards_at_all(self):
        self.assertFalse(I.may_use_any_card(0, [self.WANT], self.WANT))


if __name__ == "__main__":
    unittest.main()
