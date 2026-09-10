# -*- coding: utf-8 -*-
"""The Phase 3 block of the selftest, driven with canned verb output.

WHY THIS EXISTS. The live selftest costs about twenty views of the daily safety
number and cannot be run to find a typo. Everything the Phase 3 block does
between the verbs - which rows it reports, which it blocks, what it reads out of
a RESULT line, and whether a row that cannot be proven is ever counted as passed
- is ordinary code, and it is the code a green run would be resting on.

So the block takes its accounting functions as arguments, and this drives it
with its own. No browser opens, no verb runs, and every row's decision is made
from a string.

THE ROW THIS FILE CARES ABOUT MOST is P3-10 and P3-5's refusal to open a
conversation it cannot PROVE is already read. The rule is the one survey.py
uses: keep only rows without the unread marker, and refuse outright unless the
list also holds a row that HAS it - because a marker missing from every row is a
renamed marker, and "nothing looks unread" would then be a broken instrument
reading as a clean result, on a decision whose cost is somebody's real
conversation being marked read.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit import selftest as T


class Args(object):
    def __init__(self, **kw):
        self.other_profile = "https://www.linkedin.com/in/somebody/"
        self.follow_company = "acme"
        self.invite_name = "A Person"
        self.page = "107519091"
        self.port = 9224
        for k, v in kw.items():
            setattr(self, k, v)


def inbox_rows(unread_flags, prefix="thread-ref:"):
    out = []
    for i, u in enumerate(unread_flags):
        out.append(json.dumps({"kind": "conversation", "index": i,
                               "participant": "Person %d" % i, "last_line": "a line",
                               "when": "1:0%d PM" % i, "when_datetime": None,
                               "unread": bool(u),
                               "thread_ref": prefix + json.dumps({"who": "Person %d" % i})}))
    return "\n".join(out)


GOOD = {
    "connect-staged": (True, "RESULT connect-staged person=/in/x name='A' note_chars=40 "
                             "note_limit_stated=300 still_connectable=true "
                             "not_in_sent_tab=true pressed=nothing"),
    "connect-submit-without-a-name": (False, "FAIL --expect-name is REQUIRED with --submit"),
    "connect-wrong-name": (False, "FAIL --expect-name is 'X' and this profile's top card "
                                  "says 'Y'. These are two different people"),
    "read-inbox": (True, inbox_rows([True, False, False])
                   + "\nRESULT read-inbox rows=3 of=3 unread=1 filter=FOCUSED "
                     "unread_marker_seen=true opened_nothing=true"),
    "read-thread": (True, json.dumps({"kind": "message", "index": 0, "sender": "Them",
                                      "text": "hi", "when": "1:00 PM"})
                    + "\nRESULT read-thread messages=1 with='A' "
                      "url=https://www.linkedin.com/messaging/thread/2-a/ marked_read=true "
                      "quick_reply_rows=1"),
    "message-staged": (True, "RESULT message-staged with='A' bubbles=1 unchanged=true "
                             "draft_cleared=true chars=40 lines=1 sent=nothing"),
    "invitations": (True, json.dumps({"kind": "invitation", "name": "A Person",
                                      "profile_url": "https://www.linkedin.com/in/a/",
                                      "note": None, "when": None, "headline": "h"})
                    + "\nRESULT invitations rows=1 of=1 filter=Focused page_says=1 "
                      "with_note=0 with_when=0 pressed=nothing"),
    "follow": (True, "RESULT follow company=acme following=True was=False changed=true"),
    "unfollow": (True, "RESULT unfollow company=acme following=False was=True changed=true"),
    "invite-to-follow-staged": (True, "RESULT invite-to-follow-staged page=107519091 "
                                      "people=1 credits=50 unchanged=true "
                                      "refill='October 1, 2026' pressed=nothing"),
}


class Harness(object):
    """The accounting the block is handed, recorded rather than printed."""

    def __init__(self, canned):
        self.canned = dict(canned)
        self.reported = []
        self.passed = []
        self.failed = []
        self.blocked = []

    def attempt(self, name, fn, /, **kw):
        return self.canned.get(name, (False, "FAIL nothing canned for %s" % name))

    def step(self, row, name, fn, /, **kw):
        ok, out = self.attempt(name, fn, **kw)
        self.reported.append(row)
        (self.passed if ok else self.failed).append(row)
        return ok, out

    def check(self, row, ok, detail):
        self.reported.append(row)
        (self.passed if ok else self.failed).append((row, detail))
        return ok

    def block(self, row, why):
        self.reported.append(row)
        self.blocked.append((row, why))

    def run(self, args):
        T._phase3(args, None, self.step, self.check, self.block, self.attempt,
                  T.every, T.all_of)
        return self

    def names(self, which):
        return [r[0] if isinstance(r, tuple) else r for r in which]


class TheBlockRunsAndAccountsForEveryRow(unittest.TestCase):

    def test_a_good_run_passes_every_runnable_row_and_blocks_none(self):
        h = Harness(GOOD).run(Args())
        self.assertEqual(h.blocked, [], h.blocked)
        self.assertEqual(sorted(set(h.reported)), sorted(set(T.PHASE3_ROWS)),
                         "the rows reported are not the rows declared")
        self.assertEqual(h.names(h.failed), [], h.failed)

    def test_every_declared_runnable_row_reports_exactly_once(self):
        h = Harness(GOOD).run(Args())
        for name in T.PHASE3_ROWS:
            self.assertEqual(h.reported.count(name), 1,
                             "%s reported %d times" % (name, h.reported.count(name)))

    def test_a_missing_follow_fixture_blocks_its_row_rather_than_skipping_it(self):
        h = Harness(GOOD).run(Args(follow_company=None))
        self.assertIn("P3-12", h.names(h.blocked))
        self.assertNotIn("P3-12", h.names(h.passed))
        self.assertIn("P3-12", h.reported)

    def test_a_missing_invite_name_blocks_its_row(self):
        h = Harness(GOOD).run(Args(invite_name=None))
        self.assertIn("P3-13", h.names(h.blocked))
        self.assertNotIn("P3-13", h.names(h.passed))


class ItWillNotOpenAConversationItCannotProveIsRead(unittest.TestCase):

    def test_an_inbox_with_no_unread_row_blocks_the_thread_rows(self):
        """No positive control for the marker. "Nothing looks unread" is then a
        broken instrument, and opening a row on that basis marks a real
        conversation read."""
        canned = dict(GOOD)
        canned["read-inbox"] = (True, inbox_rows([False, False])
                                + "\nRESULT read-inbox rows=2 opened_nothing=true")
        h = Harness(canned).run(Args())
        self.assertIn("P3-10", h.names(h.blocked))
        self.assertIn("P3-5", h.names(h.blocked))
        why = dict(h.blocked)["P3-10"]
        self.assertIn("unread marker", why)

    def test_an_inbox_where_everything_is_unread_blocks_them_too(self):
        canned = dict(GOOD)
        canned["read-inbox"] = (True, inbox_rows([True, True])
                                + "\nRESULT read-inbox rows=2 opened_nothing=true")
        h = Harness(canned).run(Args())
        self.assertIn("P3-10", h.names(h.blocked))
        self.assertIn("P3-5", h.names(h.blocked))

    def test_an_empty_inbox_blocks_them(self):
        canned = dict(GOOD)
        canned["read-inbox"] = (False, "FAIL no conversation rows")
        h = Harness(canned).run(Args())
        self.assertIn("P3-10", h.names(h.blocked))
        self.assertIn("P3-5", h.names(h.blocked))

    def test_a_mixed_inbox_runs_them(self):
        """The negative control. A rule that blocked whatever the inbox looked
        like would be indistinguishable from one nobody had written."""
        h = Harness(GOOD).run(Args())
        self.assertNotIn("P3-10", h.names(h.blocked))
        self.assertNotIn("P3-5", h.names(h.blocked))
        self.assertIn("P3-10", h.names(h.passed))


class TheRowsReadWhatTheVerbsActuallySay(unittest.TestCase):

    def test_a_connect_that_did_not_prove_the_profile_survived_fails(self):
        canned = dict(GOOD)
        canned["connect-staged"] = (True, "RESULT connect-staged person=/in/x "
                                          "note_limit_stated=300 not_in_sent_tab=true "
                                          "pressed=nothing")
        h = Harness(canned).run(Args())
        self.assertIn("P3-1", h.names(h.failed))

    def test_a_connect_that_did_not_check_the_sent_tab_fails(self):
        canned = dict(GOOD)
        canned["connect-staged"] = (True, "RESULT connect-staged person=/in/x "
                                          "note_limit_stated=300 still_connectable=true "
                                          "pressed=nothing")
        h = Harness(canned).run(Args())
        self.assertIn("P3-1", h.names(h.failed))

    def test_a_connect_that_read_no_limit_off_the_page_fails(self):
        canned = dict(GOOD)
        canned["connect-staged"] = (True, "RESULT connect-staged person=/in/x "
                                          "still_connectable=true not_in_sent_tab=true "
                                          "pressed=nothing")
        h = Harness(canned).run(Args())
        self.assertIn("P3-1", h.names(h.failed))

    def test_a_wrong_name_that_was_ACCEPTED_fails_the_row(self):
        """P3-4b asserts a REFUSAL. A verb that went ahead with a mismatched
        name must turn this row red, and a row that only checked 'it returned'
        would go green on exactly that."""
        canned = dict(GOOD)
        canned["connect-wrong-name"] = (True, "RESULT connect-staged person=/in/x")
        h = Harness(canned).run(Args())
        self.assertIn("P3-4b", h.names(h.failed))

    def test_a_submit_without_a_name_that_was_ACCEPTED_fails_the_row(self):
        canned = dict(GOOD)
        canned["connect-submit-without-a-name"] = (True, "RESULT connected person=/in/x")
        h = Harness(canned).run(Args())
        self.assertIn("P3-4a", h.names(h.failed))

    def test_a_read_thread_that_hid_marked_read_fails(self):
        canned = dict(GOOD)
        canned["read-thread"] = (True, json.dumps({"kind": "message", "index": 0,
                                                   "sender": "Them", "text": "hi",
                                                   "when": "1:00 PM"})
                                 + "\nRESULT read-thread messages=1 "
                                   "url=https://www.linkedin.com/messaging/thread/2-a/")
        h = Harness(canned).run(Args())
        self.assertIn("P3-10", h.names(h.failed))

    def test_a_message_whose_thread_grew_fails(self):
        canned = dict(GOOD)
        canned["message-staged"] = (True, "RESULT message-staged with='A' bubbles=1 "
                                          "draft_cleared=true sent=nothing")
        h = Harness(canned).run(Args())
        self.assertIn("P3-5", h.names(h.failed))

    def test_a_message_that_left_its_draft_behind_fails(self):
        canned = dict(GOOD)
        canned["message-staged"] = (True, "RESULT message-staged with='A' bubbles=1 "
                                          "unchanged=true sent=nothing")
        h = Harness(canned).run(Args())
        self.assertIn("P3-5", h.names(h.failed))

    def test_an_invitations_parse_that_disagrees_with_the_page_fails(self):
        canned = dict(GOOD)
        canned["invitations"] = (True, "RESULT invitations rows=1 of=1 filter=Focused "
                                       "page_says=9 with_note=0 with_when=0 "
                                       "pressed=nothing")
        h = Harness(canned).run(Args())
        self.assertIn("P3-11", h.names(h.failed))

    def test_an_invitations_page_with_no_count_fails(self):
        canned = dict(GOOD)
        canned["invitations"] = (True, "RESULT invitations rows=1 of=1 filter=Focused "
                                       "with_note=0 pressed=nothing")
        h = Harness(canned).run(Args())
        self.assertIn("P3-11", h.names(h.failed))

    def test_a_follow_that_did_not_end_where_it_started_fails(self):
        """P3-12 borrows somebody's Page and gives it back. The row that matters
        is the LAST one."""
        canned = dict(GOOD)
        canned["unfollow"] = (True, "RESULT unfollow company=acme following=True "
                                    "was=True changed=false")
        h = Harness(canned).run(Args())
        self.assertIn("P3-12", h.names(h.failed))

    def test_a_page_already_followed_fails_the_row_rather_than_passing_quietly(self):
        """A Page the account already follows presses nothing and reports
        changed=false - correct behaviour for the verb, and the wrong FIXTURE
        for this row. It must not read as a proven follow path."""
        canned = dict(GOOD)
        canned["follow"] = (True, "RESULT follow company=acme following=True "
                                  "changed=false pressed=nothing")
        h = Harness(canned).run(Args())
        self.assertIn("P3-12", h.names(h.failed))

    def test_an_invite_that_moved_the_credits_fails_the_staged_row(self):
        canned = dict(GOOD)
        canned["invite-to-follow-staged"] = (True, "RESULT invite-to-follow-staged "
                                                   "page=1 people=1 credits=49 "
                                                   "pressed=nothing")
        h = Harness(canned).run(Args())
        self.assertIn("P3-13", h.names(h.failed))


if __name__ == "__main__":
    unittest.main()
