# -*- coding: utf-8 -*-
"""The guards on `read-inbox` and `read-thread`, against plain rows. No browser.

WHAT IS BEING GUARDED, AND WHY.

  * read-inbox must open NO conversation, and the proof is a re-read of the same
    list compared row by row. Two ways that proof can lie, each pinned here:
      - by POSITION. A new message moves a row to the top, so comparing row 3
        to row 3 compares two different people. Rows are matched by who and
        when, never by index.
      - by ABSENCE. Under the Unread filter, a conversation that gets read does
        not change class - it LEAVES the list. A comparison that only looks at
        rows present on both sides passes exactly the failure it exists to
        catch. `unread_lost` returns those rows, and the verb fails on them.
  * A thread_ref names one row by who, when, position and filter (A3). Resolving
    it opens that conversation and marks it read, so a ref that matches two
    rows must REFUSE, never pick the first.
  * A sender's name is printed on the first message of a group only. Carrying
    it forward is right; doing it silently is not, so each message says whether
    its sender was carried.

What these cannot prove: that the compose route opens nothing on the live page
today, and that the selectors still match. Those are proven on the live page,
by the RESULT line's own re-read, every run.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import inbox as I
from cc_linkedin_kit.browser import surface_kind


def row(i, who, when, unread=False, line="hi"):
    return {"index": i, "participant": who, "when": when, "unread": unread,
            "last_line": line, "unread_label": ""}


class TheReReadMatchesByWhoNotWhere(unittest.TestCase):

    def test_nothing_changed_is_clean(self):
        before = [row(0, "A", "10:01", True), row(1, "B", "Oct 1")]
        self.assertEqual(I.unread_regressions(before, before), [])
        self.assertEqual(I.unread_lost(before, before), [])

    def test_an_unread_row_that_went_read_is_caught(self):
        before = [row(0, "A", "10:01", True), row(1, "B", "Oct 1")]
        after = [row(0, "A", "10:01", False), row(1, "B", "Oct 1")]
        self.assertEqual([r["participant"] for r in I.unread_regressions(before, after)], ["A"])

    def test_a_row_that_moved_is_not_a_regression(self):
        """A new conversation arrived at the top. Index comparison would read
        B's row against A's and call A read."""
        before = [row(0, "A", "10:01", True), row(1, "B", "Oct 1")]
        after = [row(0, "C", "10:05", True), row(1, "A", "10:01", True), row(2, "B", "Oct 1")]
        self.assertEqual(I.unread_regressions(before, after), [])
        self.assertEqual(I.unread_lost(before, after), [])

    def test_a_row_that_moved_AND_went_read_is_still_caught(self):
        """An UNREAD newcomer at the top: comparing row 0 to row 0 sees unread
        on both sides and passes, while A - now row 1 - was opened."""
        before = [row(0, "A", "10:01", True), row(1, "B", "Oct 1")]
        after = [row(0, "C", "10:05", True), row(1, "A", "10:01", False), row(2, "B", "Oct 1")]
        self.assertEqual([r["participant"] for r in I.unread_regressions(before, after)], ["A"])

    def test_an_unread_row_that_vanished_is_lost_not_clean(self):
        """The Unread-filter shape: reading A removes it from the list."""
        before = [row(0, "A", "10:01", True), row(1, "B", "09:00", True)]
        after = [row(0, "B", "09:00", True)]
        self.assertEqual(I.unread_regressions(before, after), [])
        self.assertEqual([r["participant"] for r in I.unread_lost(before, after)], ["A"])

    def test_a_read_row_that_vanished_is_not_counted(self):
        before = [row(0, "A", "10:01"), row(1, "B", "09:00", True)]
        after = [row(0, "B", "09:00", True)]
        self.assertEqual(I.unread_lost(before, after), [])

    def test_two_rows_same_name_same_time_ONE_went_read(self):
        """Duplicate keys are counted, not any()-ed: one copy still unread
        must not hide the other going read (review, 2026-10-03)."""
        before = [row(0, "A", "Oct 1", True), row(1, "A", "Oct 1", True)]
        after = [row(0, "A", "Oct 1", True), row(1, "A", "Oct 1", False)]
        self.assertEqual(len(I.unread_regressions(before, after)), 1)

    def test_two_rows_same_name_same_time_both_went_read(self):
        before = [row(0, "A", "Oct 1", True), row(1, "A", "Oct 1", True)]
        after = [row(0, "A", "Oct 1", False), row(1, "A", "Oct 1", False)]
        self.assertEqual(len(I.unread_regressions(before, after)), 2)


class TheBaselineIsFirstSight(unittest.TestCase):
    """Review defect 1, 2026-10-03. The baseline used to be the LAST snapshot
    before the re-read, taken after every scroll - so a row opened during the
    scrolls was already read in the baseline, and the proof found nothing."""

    def test_a_row_opened_during_the_scrolls_is_caught(self):
        load = [row(0, "A", "10:01", True), row(1, "B", "Oct 1")]
        after_scroll = [row(0, "A", "10:01", False), row(1, "B", "Oct 1"), row(2, "C", "Sep 9")]
        end = after_scroll
        base = I.first_sight([load, after_scroll])
        self.assertEqual([r["participant"] for r in I.unread_regressions(base, end)], ["A"])
        # and the old baseline would have passed it:
        self.assertEqual(I.unread_regressions(after_scroll, end), [])

    def test_rows_that_appear_later_are_taken_from_where_they_appear(self):
        base = I.first_sight([[row(0, "A", "1")], [row(0, "A", "1"), row(1, "B", "2", True)]])
        self.assertEqual([(r["participant"], r["unread"]) for r in base],
                         [("A", False), ("B", True)])

    def test_the_pre_filter_list_counts(self):
        """An unread row seen before the Unread filter was pressed must still be
        unread and present at the end."""
        pre = [row(0, "A", "10:01", True), row(1, "B", "Oct 1")]
        filtered = [row(0, "A", "10:01", True)]
        end = []
        base = I.first_sight([pre, filtered])
        self.assertEqual([r["participant"] for r in I.unread_lost(base, end)], ["A"])

    def test_duplicates_are_kept(self):
        base = I.first_sight([[row(0, "A", "1", True)],
                              [row(0, "A", "1", True), row(1, "A", "1", True)]])
        self.assertEqual(len(base), 2)


class AnEmptyThreadReadFails(unittest.TestCase):
    """Rule 4, review defect 7: a body selector that moved still counts twenty
    messages, each with empty text, and that must not be a read."""

    def test_no_text_anywhere_fails(self):
        msgs = [{"sender": "A", "text": "", "urn": "u1"}, {"sender": "A", "text": "", "urn": "u2"}]
        self.assertIn("NOT ONE carries text", I.message_problem(msgs))

    def test_one_empty_text_among_many_is_fine(self):
        """An image or an attachment-only message has no text, legitimately."""
        msgs = [{"sender": "A", "text": "hi", "urn": "u1"}, {"sender": "B", "text": "", "urn": "u2"}]
        self.assertIsNone(I.message_problem(msgs))

    def test_no_messages_fails(self):
        self.assertTrue(I.message_problem([]))

    def test_a_blank_sender_fails(self):
        msgs = [{"sender": "", "text": "hi", "urn": "u1"}]
        self.assertIn("no sender", I.message_problem(msgs))


class TheOpenedConversationIsThePerson(unittest.TestCase):
    """Review defect 5: the check used to be skipped when the header was empty,
    and was a substring of the first name when it ran."""

    def test_exact_match(self):
        self.assertTrue(I.same_person("Jane Doe", " Jane  Doe "))

    def test_a_substring_is_not_the_person(self):
        self.assertFalse(I.same_person("Ann", "Joanne Smith"))
        self.assertFalse(I.same_person("Jane Doe", "Jane Doe, Bob Roe"))

    def test_an_empty_side_is_never_a_match(self):
        self.assertFalse(I.same_person("Jane Doe", ""))
        self.assertFalse(I.same_person("", ""))


class TheThreadRefIsOpaqueAndStrict(unittest.TestCase):

    def test_round_trip(self):
        ref = I.make_ref(row(3, "Jane  Doe", " Sep 30 "), "unread")
        self.assertTrue(ref.startswith("tr1."))
        self.assertNotIn("Jane", ref)
        self.assertEqual(I.parse_ref(ref), {"p": "Jane Doe", "w": "Sep 30", "i": 3, "f": "unread"})

    def test_a_url_is_not_a_ref(self):
        with self.assertRaises(ValueError):
            I.parse_ref("https://www.linkedin.com/messaging/thread/2-abc==/")

    def test_a_damaged_ref_refuses(self):
        with self.assertRaises(ValueError):
            I.parse_ref("tr1.!!!notbase64")
        with self.assertRaises(ValueError):
            I.parse_ref(I.REF_PREFIX + "e30")   # {} - decodes, carries nothing

    def test_a_bad_filter_refuses(self):
        import base64
        import json
        raw = base64.urlsafe_b64encode(json.dumps(
            {"p": "A", "w": "x", "i": 0, "f": "archived"}).encode()).decode().rstrip("=")
        with self.assertRaises(ValueError):
            I.parse_ref(I.REF_PREFIX + raw)

    def test_resolves_by_who_and_when_after_the_row_moved(self):
        ref = I.parse_ref(I.make_ref(row(0, "A", "10:01"), "all"))
        rows = [row(0, "C", "10:05"), row(1, "A", "10:01")]
        self.assertEqual(I.match_ref(rows, ref), (1, None))

    def test_a_newer_message_makes_the_ref_stale_and_says_so(self):
        ref = I.parse_ref(I.make_ref(row(0, "A", "10:01"), "all"))
        idx, why = I.match_ref([row(0, "A", "10:40")], ref)
        self.assertIsNone(idx)
        self.assertIn("read-inbox again", why)

    def test_a_missing_person_refuses(self):
        ref = I.parse_ref(I.make_ref(row(0, "A", "10:01"), "all"))
        idx, why = I.match_ref([row(0, "B", "10:01")], ref)
        self.assertIsNone(idx)

    def test_two_identical_rows_use_position_to_break_the_tie(self):
        ref = I.parse_ref(I.make_ref(row(1, "A", "Oct 1"), "all"))
        rows = [row(0, "A", "Oct 1"), row(1, "A", "Oct 1")]
        self.assertEqual(I.match_ref(rows, ref), (1, None))

    def test_two_identical_rows_and_the_position_moved_REFUSES(self):
        """The wrong guess opens a stranger's conversation and marks it read."""
        ref = I.parse_ref(I.make_ref(row(5, "A", "Oct 1"), "all"))
        rows = [row(0, "A", "Oct 1"), row(1, "A", "Oct 1")]
        idx, why = I.match_ref(rows, ref)
        self.assertIsNone(idx)
        self.assertIn("refusing to guess", why)


class SendersAreCarriedOutLoud(unittest.TestCase):

    def test_carried_forward_and_flagged(self):
        got = I.carry_senders([
            {"sender": "A", "sender_url": "/in/a", "text": "1"},
            {"sender": "", "sender_url": "", "text": "2"},
            {"sender": "B", "sender_url": "/in/b", "text": "3"},
        ])
        self.assertEqual([(m["sender"], m["sender_carried"]) for m in got],
                         [("A", False), ("A", True), ("B", False)])
        self.assertEqual(got[1]["sender_url"], "/in/a")

    def test_nothing_to_carry_stays_blank(self):
        """So the verb's blank-sender check fails the run instead of inventing one."""
        got = I.carry_senders([{"sender": "", "sender_url": "", "text": "1"}])
        self.assertEqual(got[0]["sender"], "")


class SmallParsers(unittest.TestCase):

    def test_unread_count(self):
        self.assertEqual(I.unread_count("3 unread messages"), 3)
        self.assertEqual(I.unread_count("1 unread message"), 1)
        self.assertIsNone(I.unread_count(""))

    def test_thread_url_shape(self):
        self.assertTrue(I.THREAD_PATH.match("https://www.linkedin.com/messaging/thread/2-abc==/"))
        self.assertTrue(I.THREAD_PATH.match("https://www.linkedin.com/messaging/thread/2-abc==/?x=1"))
        self.assertFalse(I.THREAD_PATH.match("https://www.linkedin.com/messaging/compose/"))
        self.assertFalse(I.THREAD_PATH.match("https://linkedin.com.evil.test/messaging/thread/2-a/"))


class TheUnreadDraftIsNotAConversation(unittest.TestCase):
    """Measured 2026-10-03: the Unread filter moves the address to
    /messaging/thread/new/?filter=unread with no conversation open. Treating
    that as a conversation fails a clean read-inbox, and lets read-thread's wait
    for a conversation pass before any row was clicked."""

    def test_the_draft_is_not_a_conversation(self):
        self.assertFalse(I.is_conversation_url(
            "https://www.linkedin.com/messaging/thread/new/?filter=unread"))
        self.assertFalse(I.is_conversation_url("https://www.linkedin.com/messaging/thread/new/"))
        self.assertFalse(I.is_conversation_url("https://www.linkedin.com/messaging/compose/"))

    def test_the_thread_id_is_compared_not_just_the_shape(self):
        """Review defect 6: landing on a DIFFERENT conversation must not pass."""
        a = I.thread_id("https://www.linkedin.com/messaging/thread/2-abc==/")
        self.assertEqual(a, "2-abc==")
        self.assertEqual(a, I.thread_id("https://www.linkedin.com/messaging/thread/2-abc==?x=1"))
        self.assertNotEqual(a, I.thread_id("https://www.linkedin.com/messaging/thread/2-xyz==/"))
        self.assertIsNone(I.thread_id("https://www.linkedin.com/messaging/compose/"))

    def test_a_real_thread_is(self):
        self.assertTrue(I.is_conversation_url(
            "https://www.linkedin.com/messaging/thread/2-abc==/?filter=unread"))
        self.assertTrue(I.is_conversation_url(
            "https://www.linkedin.com/messaging/thread/newsletter-like-id/"))


class TheCountersTheseVerbsLandOn(unittest.TestCase):
    """Decided by surface_kind, never here. Pinned so a change there is seen."""

    def test_the_list_route_is_uncapped_because_it_opens_nothing(self):
        self.assertEqual(surface_kind(I.COMPOSE_URL), "view_self")

    def test_the_unread_filters_draft_is_uncapped_by_ruling(self):
        """Owner ruling 2026-10-03, docs/ruling-unread-draft-2026-10-03.md."""
        self.assertEqual(surface_kind(I.UNREAD_PILL_URL), "view_self")

    def test_a_thread_is_capped(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/thread/2-abc==/"), "view")


if __name__ == "__main__":
    unittest.main()
