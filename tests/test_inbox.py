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
  * The list is VIRTUALISED (devthrottle#4541): a row the viewport has not
    reached is an empty placeholder. A reader that jumps to the bottom and
    counts the cards it finds drops every row it jumped over and still prints
    RESULT. Rows are held by POSITION, a position never read fails the run,
    and a position that changes hands mid-run fails it too. `FakeVirtualList`
    below is the measured page in miniature, and the old jump is run against
    it to show the drop.
  * One person on two rows (devthrottle#3277) is told apart by the last line,
    then by position, and is refused only when neither can; and the refusal
    names the way round it, read-thread on the person's profile URL.
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
        self.assertEqual(I.parse_ref(ref), {"p": "Jane Doe", "w": "Sep 30", "i": 3, "f": "unread",
                                            "l": I.line_tag("hi")})
        self.assertNotIn("hi", I.parse_ref(ref)["l"])

    def test_a_ref_from_before_the_line_tag_still_parses(self):
        import base64
        import json
        raw = base64.urlsafe_b64encode(json.dumps(
            {"p": "A", "w": "Oct 1", "i": 2, "f": "all"}).encode()).decode().rstrip("=")
        self.assertEqual(I.parse_ref(I.REF_PREFIX + raw)["l"], "")

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
        self.assertIn("profile URL", why)


class OnePersonOnTwoRows(unittest.TestCase):
    """devthrottle#3277: the same name at the same time on two rows. The old
    ref could only use position, and position was the count of RENDERED cards,
    which the virtualised list changes from one read to the next."""

    def test_the_last_line_tells_them_apart_after_both_moved(self):
        ref = I.parse_ref(I.make_ref(row(6, "A", "Oct 22", line="A: hello there"), "all"))
        rows = [row(0, "N", "now"), row(7, "A", "Oct 22", line="A: hello there"),
                row(19, "A", "Oct 22", line="")]
        self.assertEqual(I.match_ref(rows, ref), (7, None))

    def test_the_row_with_no_snippet_is_reachable_too(self):
        ref = I.parse_ref(I.make_ref(row(18, "A", "Oct 22", line=""), "all"))
        rows = [row(6, "A", "Oct 22", line="A: hello there"), row(18, "A", "Oct 22", line="")]
        self.assertEqual(I.match_ref(rows, ref), (18, None))

    def test_no_snippet_has_a_tag_of_its_own(self):
        """'' is an old ref with no tag; a row with no snippet must still be
        told from its twin when both have moved (review finding 6)."""
        self.assertEqual(I.line_tag(""), I.NO_LINE)
        ref = I.parse_ref(I.make_ref(row(18, "A", "Oct 22", line=""), "all"))
        rows = [row(7, "A", "Oct 22", line="A: hello there"), row(19, "A", "Oct 22", line="")]
        self.assertEqual(I.match_ref(rows, ref), (19, None))

    def test_one_row_in_view_with_another_line_is_refused(self):
        """The twin of the ref's row is the only one in view: same person, same
        time, the other conversation. Opening it marks the wrong one read
        (review finding 5)."""
        ref = I.parse_ref(I.make_ref(row(7, "A", "Oct 22", line="A: hello there"), "all"))
        idx, why = I.match_ref([row(7, "A", "Oct 22", line="")], ref)
        self.assertIsNone(idx)
        self.assertIn("different last line", why)

    def test_an_old_ref_with_no_tag_still_opens_the_one_row(self):
        ref = {"p": "A", "w": "Oct 22", "i": 3, "f": "all", "l": ""}
        self.assertEqual(I.match_ref([row(9, "A", "Oct 22", line="x")], ref), (9, None))

    def test_same_line_too_falls_back_to_position(self):
        ref = I.parse_ref(I.make_ref(row(3, "A", "Oct 1", line="x"), "all"))
        rows = [row(1, "A", "Oct 1", line="x"), row(3, "A", "Oct 1", line="x")]
        self.assertEqual(I.match_ref(rows, ref), (3, None))

    def test_a_newer_message_on_one_of_two_rows_names_both_times(self):
        ref = I.parse_ref(I.make_ref(row(3, "A", "Oct 1"), "all"))
        idx, why = I.match_ref([row(0, "A", "10:40"), row(5, "A", "Sep 2")], ref)
        self.assertIsNone(idx)
        self.assertIn("'10:40' and 'Sep 2'", why)


class TheListIsHeldByPosition(unittest.TestCase):

    def test_a_later_read_of_the_same_row_wins(self):
        held = {}
        self.assertEqual(I.merge_positions(held, [row(0, "A", "1", line="")]), [])
        self.assertEqual(I.merge_positions(held, [row(0, "A", "1", line="A: hi")]), [])
        self.assertEqual(held[0]["last_line"], "A: hi")

    def test_a_position_that_changes_hands_is_reported(self):
        held = {}
        I.merge_positions(held, [row(0, "A", "1"), row(1, "B", "2")])
        self.assertEqual(I.merge_positions(held, [row(0, "C", "3"), row(1, "A", "1")]), [0, 1])

    def test_a_new_message_in_the_top_row_is_not_a_shift(self):
        """Its time and snippet change; nobody moved (review finding 7)."""
        held = {}
        I.merge_positions(held, [row(0, "A", "Oct 27", line="old")])
        self.assertEqual(I.merge_positions(held, [row(0, "A", "6:01 PM", line="new")]), [])
        self.assertEqual(held[0]["when"], "6:01 PM")

    def test_gaps(self):
        held = {0: row(0, "A", "1"), 2: row(2, "C", "3")}
        self.assertEqual(I.list_gaps(held, 4), [1, 3])
        self.assertEqual(I.list_gaps(held, 1), [])


class FakeVirtualList(object):
    """The conversation list as measured on 2026-10-27 (devthrottle#4541), in
    miniature. The page has fetched `loaded` conversations (20 more each time
    the viewport sits at the bottom); a fetched row is an empty placeholder
    until the viewport has covered it, and then stays rendered. The viewport
    shows `view` rows and a step moves it half that - or, as the old reader
    did, straight to the bottom.

    STAYS RENDERED is the measured behaviour this models, not a promise. The
    verb does not trust it: its final read must still show every position it
    printed, and `recycle` here makes a list that breaks it, to prove that
    fails. A live run failing on "no longer rendered" means LinkedIn has
    started recycling rows."""

    def __init__(self, people, view=8, page=20, shift_at=None, recycle=False):
        self.people = list(people)
        self.view, self.page_size = view, page
        self.loaded = min(page, len(self.people))
        self.top = 0
        self.rendered = set(range(min(view, self.loaded)))
        self.steps = 0
        self.shift_at = shift_at      # a new message lifts a row to the top at this step
        self.recycle = recycle        # rows far above the viewport go back to placeholders

    def step(self, jump=False):
        self.steps += 1
        if self.shift_at == self.steps:
            self.people.insert(0, self.people.pop(self.loaded - 1))
        bottom = max(0, self.loaded - self.view)
        if self.top >= bottom:
            if self.loaded < len(self.people):
                self.loaded = min(self.loaded + self.page_size, len(self.people))
            return {"moved": 0}
        old = self.top
        self.top = bottom if jump else min(bottom, self.top + self.view // 2)
        self.rendered |= set(range(self.top, min(self.top + self.view, self.loaded)))
        if self.recycle:
            self.rendered = {i for i in self.rendered if i >= self.top - self.view}
        return {"moved": self.top - old}

    def snap(self):
        rows = [row(i, self.people[i][0], self.people[i][1]) for i in sorted(self.rendered)
                if i < self.loaded]
        return {"url": I.COMPOSE_URL, "thread_pane": False, "draft": True, "active": 0,
                "positions": self.loaded, "cards": len(rows), "rows": rows}


class FakeListPage(object):
    def __init__(self, lst, jump=False):
        self.lst, self.jump = lst, jump

    def evaluate(self, js, arg=None):
        if js is I.STEP_LIST_JS:
            return self.lst.step(self.jump)
        if js is I.ROWS_JS:
            return self.lst.snap()
        raise AssertionError("unexpected script")


class FakeListBrowser(object):
    def __init__(self, lst, jump=False):
        self.page = FakeListPage(lst, jump)


PEOPLE = [("P%02d" % i, "Oct %d" % (30 - i // 4)) for i in range(60)]


class TheVirtualListIsWalkedNotJumped(unittest.TestCase):

    def walk(self, lst, want, jump=False):
        from unittest import mock
        br = FakeListBrowser(lst, jump)
        first = I._read_rows(br)
        with mock.patch.object(I.time, "sleep"), \
                mock.patch.object(I, "_assert_nothing_open"):
            snap, held, ended = I._load_rows(br, want, first, [first["rows"]])
        self.ended = ended
        return snap, held

    def test_the_old_jump_drops_rows_that_exist(self):
        """What happened on 2026-10-27: jumping straight to the bottom leaves
        the rows in between as placeholders, and a reader of cards only never
        knows they were there. The gap check is what now refuses it."""
        snap, held = self.walk(FakeVirtualList(PEOPLE), 50, jump=True)
        self.assertGreater(len(I.list_gaps(held, 50)), 0)

    def test_the_walk_reads_every_position(self):
        snap, held = self.walk(FakeVirtualList(PEOPLE), 50)
        self.assertEqual(I.list_gaps(held, 50), [])
        self.assertEqual([held[i]["participant"] for i in range(50)],
                         [p for p, _ in PEOPLE[:50]])

    def test_a_list_shorter_than_the_limit_ends(self):
        snap, held = self.walk(FakeVirtualList(PEOPLE[:13]), 100)
        self.assertEqual(snap["positions"], 13)
        self.assertEqual(I.list_gaps(held, 13), [])
        self.assertEqual(self.ended, "bottom")

    def test_a_list_that_moves_mid_walk_fails(self):
        import contextlib
        import io
        out = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(out):
            self.walk(FakeVirtualList(PEOPLE, shift_at=3), 50)
        self.assertIn("showed a different conversation", out.getvalue())

    def test_a_list_that_does_not_scroll_says_so(self):
        lst = FakeVirtualList(PEOPLE)
        br = FakeListBrowser(lst)
        first = I._read_rows(br)
        real = br.page.evaluate
        br.page.evaluate = lambda js, arg=None: None if js is I.STEP_LIST_JS else real(js, arg)
        _, held, ended = I._load_rows(br, 50, first, [first["rows"]])
        self.assertEqual(ended, "no-scroll")
        self.assertIn("scrolling ancestor", I.STOPPED[ended])

    def test_a_card_outside_any_list_item_fails(self):
        """The item selector moved: the positions would silently shrink."""
        lst = FakeVirtualList(PEOPLE)
        snap = lst.snap()
        snap["cards"] += 1
        br = FakeListBrowser(lst)
        br.page.evaluate = lambda js, arg=None: snap
        with self.assertRaises(SystemExit):
            I._read_rows(br)


class ReadInboxEndToEnd(unittest.TestCase):
    """The whole verb against the fake list: the RESULT line, and the checks
    that stand between a walk and that line (review finding 10a)."""

    def run_it(self, lst, limit, jump=False):
        import contextlib
        import io
        from types import SimpleNamespace
        from unittest import mock
        br = FakeListBrowser(lst, jump)

        class Br(object):
            page = br.page

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def open_list(b, pace, unread):
            first = I._read_rows(b)
            return first, [first["rows"]]

        out = io.StringIO()
        code = None
        with mock.patch.object(I, "Browser", lambda port: Br()), \
                mock.patch.object(I, "Pace", lambda: None), \
                mock.patch.object(I, "_open_list", open_list), \
                mock.patch.object(I, "_assert_nothing_open"), \
                mock.patch.object(I.time, "sleep"), contextlib.redirect_stdout(out):
            try:
                I.read_inbox(SimpleNamespace(limit=limit, unread=False, port=9224))
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue().splitlines()

    def test_every_row_and_gaps_zero(self):
        code, lines = self.run_it(FakeVirtualList(PEOPLE), 50)
        self.assertIsNone(code)
        self.assertEqual(len(lines), 51)
        self.assertTrue(lines[-1].startswith("RESULT inbox rows=50 unread=0 filter=all gaps=0 "
                                             "end=limit "))
        import json
        self.assertEqual([json.loads(l)["participant"] for l in lines[:-1]],
                         [p for p, _ in PEOPLE[:50]])

    def test_a_short_list_says_it_ended(self):
        code, lines = self.run_it(FakeVirtualList(PEOPLE[:13]), 100)
        self.assertIsNone(code)
        self.assertIn("rows=13 ", lines[-1])
        self.assertIn("end=bottom", lines[-1])

    def test_an_empty_list_is_a_failure_not_an_empty_inbox(self):
        code, lines = self.run_it(FakeVirtualList([]), 20)
        self.assertEqual(code, 1)
        self.assertIn("no conversations on the all list", lines[-1])

    def test_rows_that_were_never_rendered_fail_with_no_result(self):
        """What 2026-10-27 printed as success: the jump reader's gaps."""
        code, lines = self.run_it(FakeVirtualList(PEOPLE), 50, jump=True)
        self.assertEqual(code, 1)
        self.assertTrue(lines[-1].startswith("FAIL "))
        self.assertIn("never rendered", lines[-1])
        self.assertFalse(any(l.startswith("RESULT") for l in lines))

    def test_rows_the_list_recycled_fail(self):
        """Review finding 1: a row read early and gone at the end proves nothing
        about whether the list shifted in between."""
        code, lines = self.run_it(FakeVirtualList(PEOPLE, recycle=True), 50)
        self.assertEqual(code, 1)
        self.assertIn("no longer rendered", lines[-1])


class ReadThreadFromAProfile(unittest.TestCase):
    """devthrottle#4541 ask 2: a conversation the list does not show can be read
    from the person's profile. Faked past the open, which is `message`'s own
    profile route (tested in test_message.py): the records and the RESULT."""

    def run_it(self, msgs):
        import contextlib
        import io
        from types import SimpleNamespace
        from unittest import mock
        url = "https://www.linkedin.com/messaging/compose/?profileUrn=x&recipient=x"

        class Loc(object):
            first = property(lambda self: self)

            def wait_for(self, **kw):
                return None

        class Page(object):
            def __init__(self):
                self.url = url

            def locator(self, sel):
                return Loc()

            def evaluate(self, js, arg=None):
                if js is I.MESSAGES_JS:
                    return {"found": True, "events": len(msgs), "messages": msgs}
                if js is I.SCROLL_THREAD_UP_JS:
                    return False
                if js is I.HEADER_JS:
                    return {"header": "", "active_row": ""}
                raise AssertionError("unexpected script")

        class Br(object):
            page = Page()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        run = SimpleNamespace(shown_url=lambda: url)
        opened = []

        def from_profile(br, pace, target):
            opened.append(target)
            return run, "Ann Lee", "Me Owner"

        out = io.StringIO()
        with mock.patch.object(I, "Browser", lambda port: Br()), \
                mock.patch.object(I, "Pace", lambda: None), \
                mock.patch.object(I, "_open_from_ref", lambda *a: opened.append("ref")), \
                mock.patch.object(I, "_open_from_profile", from_profile), \
                mock.patch.object(I.time, "sleep"), contextlib.redirect_stdout(out):
            I.read_thread(SimpleNamespace(target="https://www.linkedin.com/in/ann-lee/",
                                          port=9224))
        return opened, out.getvalue().splitlines()

    def msg(self, sender, text, urn):
        return {"sender": sender, "sender_url": "/in/x", "time": "1:00 PM", "day": "Oct 22",
                "text": text, "urn": urn}

    def test_the_profile_route_prints_the_messages_and_says_how(self):
        opened, lines = self.run_it([self.msg("Me Owner", "hello", "u1"),
                                     self.msg("Ann Lee", "hi back", "u2")])
        self.assertEqual(opened, ["https://www.linkedin.com/in/ann-lee/"])
        self.assertEqual(len(lines), 3)
        self.assertIn('"kind": "message"', lines[0])
        self.assertTrue(lines[2].startswith('RESULT thread messages=2 complete=true '
                                            'participant="Ann Lee"'))
        self.assertIn("marked_read=true", lines[2])
        self.assertIn("via=profile", lines[2])

    def test_a_third_sender_is_the_wrong_conversation(self):
        with self.assertRaises(SystemExit):
            self.run_it([self.msg("Me Owner", "hello", "u1"),
                         self.msg("Somebody Else", "hi", "u2")])


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
