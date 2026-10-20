# -*- coding: utf-8 -*-
"""The guards on `connect`, against plain values and a fake run. No browser.

WHAT IS BEING GUARDED, AND WHY.

  * THE STRANGER'S Connect. A profile page is full of OTHER people's invite
    links (survey section 2, trap 2). The invitation page must be for the slug
    that was asked for, or the run refuses before opening it.
  * The pre-check is read-profile's own answer, mapped onto outcomes: 1st
    degree is already-connected, a Pending control is already-pending, and
    every "cannot read it" is a refusal - never a go.
  * THE NOTE LIMIT IS THE PAGE'S. Two readings of it must agree, and a limit
    that cannot be read refuses rather than types and hopes.
  * --submit names its target twice, and that refusal happens BEFORE a browser
    is attached.
  * A STAGED RUN PRESSES NO SEND CONTROL and reserves no outbound slot,
    whatever it meets. A submitted run presses exactly the control that
    matches the note, and only a Pending control after the reload is a send.
  * Nothing in the verb presses a key in the note box, and nothing in the
    selftest ever passes submit=True. Both are properties of the SOURCE, so
    they are checked against the source.

What these cannot prove: that the modal still looks the way it was measured on
2026-10-20, and that pressing Send creates an invitation. The first is the live
staged run; the second has not been run against a real person at all, because
the owner has not named a consenting one (design row P3-2 is BLOCKED).
"""
import argparse
import io
import os
import re
import shutil
import sys
import tempfile
import tokenize
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import browser as B
from cc_linkedin_kit import connections as N
from cc_linkedin_kit import selectors as S

SLUG = "jane-example"
URL = "https://www.linkedin.com/preload/custom-invite/?vanityName=jane-example"

# The modal's text, measured 2026-10-20, with the person's name replaced.
FIRST = ("Dialog content start. Add a note to your invitation? Personalize your invitation to "
         "Jane Example by adding a note. LinkedIn members are more likely to accept "
         "invitations that include a note. You have unlimited notes with Premium Add a note "
         "Send without a note Dialog content end.")
NOTE_STATE = ("Dialog content start. Add a note to your invitation Please limit personal note to "
              "300 characters. LinkedIn members are more likely to accept invitations that "
              "include a personal note. 0/300 Cancel Send Dialog content end.")


class Precheck(unittest.TestCase):

    def go(self, **kw):
        args = dict(degree="2nd", can_connect=True, reason="an invite control is on the top card",
                    pending=False, via="topcard", url=URL, slug=SLUG)
        args.update(kw)
        return N.decide_precheck(**args)

    def test_a_positively_seen_invite_for_this_person_goes(self):
        self.assertEqual(self.go(), ("go", None))
        self.assertEqual(self.go(via="more-menu")[0], "go")

    def test_first_degree_is_already_connected_and_not_a_refusal(self):
        self.assertEqual(self.go(degree="1st", can_connect=False)[0], "already-connected")

    def test_pending_is_already_pending(self):
        self.assertEqual(self.go(can_connect=False, pending=True)[0], "already-pending")

    def test_own_profile_refuses(self):
        with self.assertRaises(N.Refused):
            self.go(degree="self", can_connect=None)

    def test_an_undecided_control_refuses_and_is_not_a_go(self):
        with self.assertRaises(N.Refused):
            self.go(can_connect=None, reason="disabled")

    def test_no_invite_control_refuses(self):
        with self.assertRaises(N.Refused):
            self.go(can_connect=False, reason="no invite control")

    def test_a_strangers_invitation_page_refuses(self):
        # Survey trap 2: the rail's suggestion cards carry other people's links.
        with self.assertRaises(N.Refused):
            self.go(url=URL.replace("jane-example", "someone-else"))

    def test_an_invitation_url_that_is_not_custom_invite_refuses(self):
        with self.assertRaises(N.Refused):
            self.go(url="https://www.linkedin.com/in/jane-example/")

    def test_an_unmeasured_location_refuses(self):
        with self.assertRaises(N.Refused):
            self.go(via="sticky-header")


class Parsing(unittest.TestCase):

    def test_invite_slug(self):
        self.assertEqual(N.invite_slug(URL), SLUG)
        self.assertEqual(N.invite_slug("/preload/custom-invite/?vanityName=J%C3%B6rg-x"), "jörg-x")
        self.assertEqual(N.invite_slug("/preload/custom-invite/?a=1&vanityName=ab&b=2"), "ab")
        self.assertIsNone(N.invite_slug("https://www.linkedin.com/in/jane-example/"))

    def test_modal_name_is_read_from_the_first_state(self):
        self.assertEqual(N.modal_name(FIRST), "Jane Example")
        self.assertIsNone(N.modal_name(NOTE_STATE))

    def test_page_length_counts_like_javascript(self):
        self.assertEqual(N.page_length("abcd"), 4)
        self.assertEqual(N.page_length("é"), 1)
        self.assertEqual(N.page_length("\U0001F600"), 2)     # outside the basic plane

    def test_counter_value(self):
        self.assertEqual(N.counter_value(["110/300"]), 110)
        self.assertIsNone(N.counter_value(["Premium"]))


class NoteLimit(unittest.TestCase):

    def test_sentence_and_counter_agree(self):
        self.assertEqual(N.note_limit(NOTE_STATE, ["0/300"]), 300)

    def test_either_alone_is_read(self):
        self.assertEqual(N.note_limit(NOTE_STATE, []), 300)
        self.assertEqual(N.note_limit("no sentence", ["0/200"]), 200)

    def test_two_limits_that_disagree_refuse(self):
        with self.assertRaises(N.Refused):
            N.note_limit(NOTE_STATE, ["0/200"])

    def test_two_counters_refuse(self):
        with self.assertRaises(N.Refused):
            N.note_limit("", ["0/200", "0/300"])

    def test_no_limit_at_all_refuses_rather_than_types(self):
        with self.assertRaises(N.Refused):
            N.note_limit("Add a note to your invitation", [])


def modal_state(**kw):
    st = {"modals": 1, "text": FIRST, "value": None, "counters": [], "boxes": 0,
          "buttons": [{"name": n, "disabled": False}
                      for n in (S.INVITE_DISMISS, S.INVITE_ADD_NOTE, S.INVITE_SEND_BARE)]}
    st.update(kw)
    return st


def typed_state(value, counter, send_disabled=False):
    return modal_state(text=NOTE_STATE, value=value, boxes=1, counters=[counter],
                       buttons=[{"name": S.INVITE_DISMISS, "disabled": False},
                                {"name": S.INVITE_CANCEL_NOTE, "disabled": False},
                                {"name": S.INVITE_SEND_NOTE, "disabled": send_disabled}])


class ModalChecks(unittest.TestCase):
    """The modal's checks as values (review finding 2): each one passes on what
    was measured and fails on the one thing that differs."""

    def test_the_measured_modal_passes(self):
        self.assertIsNone(N.modal_problem(modal_state(), "Jane Example"))

    def test_two_modals_fail(self):
        self.assertIsNotNone(N.modal_problem(modal_state(modals=2), "Jane Example"))

    def test_a_modal_naming_someone_else_fails(self):
        self.assertIsNotNone(N.modal_problem(modal_state(), "Joanne Example"))

    def test_an_unmeasured_button_set_fails(self):
        st = modal_state()
        st["buttons"].append({"name": "Verify email", "disabled": False})
        self.assertIsNotNone(N.modal_problem(st, "Jane Example"))

    def test_the_box_must_be_one_and_empty(self):
        self.assertIsNone(N.box_problem(modal_state(boxes=1, value="")))
        self.assertIsNotNone(N.box_problem(modal_state(boxes=2, value="")))
        self.assertIsNotNone(N.box_problem(modal_state(boxes=1, value="left over")))

    def test_the_readback(self):
        note = "Glad to connect."
        self.assertIsNone(N.readback_problem(note, typed_state(note, "16/300")))
        self.assertIsNotNone(N.readback_problem(note, typed_state(note[:-1], "15/300")))
        self.assertIsNotNone(N.readback_problem(note, typed_state(note, "15/300")))
        self.assertIsNotNone(N.readback_problem(note, typed_state(note, "16/300", True)))

    def test_exactly_one_visible_button(self):
        self.assertIsNone(N.visible_one(1, "Dismiss"))
        self.assertIsNotNone(N.visible_one(0, "Dismiss"))
        self.assertIsNotNone(N.visible_one(2, "Dismiss"))


class LoadNote(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cc-linkedin-note-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, raw):
        p = os.path.join(self.dir, "n.txt")
        with open(p, "wb") as f:
            f.write(raw)
        return p

    def test_no_note_is_none(self):
        self.assertIsNone(N.load_note(None, None))

    def test_a_bom_and_crlf_are_not_part_of_the_note(self):
        p = self.write(b"\xef\xbb\xbfHi Jane,\r\nglad to connect.  \r\n")
        self.assertEqual(N.load_note(None, p), "Hi Jane,\nglad to connect.")

    def test_invisible_characters_refuse(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            N.load_note("Hi​Jane", None)

    def test_an_empty_note_refuses(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            N.load_note("   \n ", None)


def args(**kw):
    a = {"url": SLUG, "note": None, "note_file": None, "expect_name": None,
         "submit": False, "shot": None, "port": 9224}
    a.update(kw)
    return argparse.Namespace(**a)


class BeforeTheBrowser(unittest.TestCase):
    """Refusals that must happen before anything is attached or opened."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cc-linkedin-connect-")
        self._state, B.STATE_DIR = B.STATE_DIR, self.dir
        self._browser = N.Browser
        N.Browser = self.no_browser

    def tearDown(self):
        N.Browser = self._browser
        B.STATE_DIR = self._state
        shutil.rmtree(self.dir, ignore_errors=True)

    @staticmethod
    def no_browser(*a, **k):
        raise AssertionError("a browser was attached before the refusal")

    def run_it(self, a):
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            N.connect(a)
        return cm.exception.code, buf.getvalue()

    def test_submit_without_expect_name_refuses_first(self):
        code, out = self.run_it(args(submit=True))
        self.assertEqual(code, 1)
        self.assertIn("RESULT connect refused", out)
        self.assertIn("sent=nothing", out)

    def test_the_daily_cap_refuses_a_submit_before_opening_anything(self):
        p = B.Pace()
        for _ in range(B.Pace.CAPS["connect"]):
            p._reserve("connect", None, "connect")
        code, out = self.run_it(args(submit=True, expect_name="Jane Example"))
        self.assertEqual(code, 1)
        self.assertIn("daily cap reached for connect", out)

    def test_the_view_cap_refuses_a_run_it_could_not_prove(self):
        p = B.Pace()
        for _ in range(B.Pace.VIEW_CAP - N.VIEWS_PER_RUN + 1):
            p._reserve("view", None, "views")
        code, out = self.run_it(args())
        self.assertEqual(code, 1)
        self.assertIn("view cap", out)

    def test_the_cap_is_the_owners_fifteen(self):
        self.assertEqual(B.Pace.CAPS["connect"], 15)


# ---------------------------------------------------------------- a fake run

class FakePace(object):
    def __init__(self):
        self.outbound = []

    def before(self, kind):
        self.outbound.append(("before", kind))
        if getattr(self, "run", None) is not None and self.run.after_gap:
            self.run.after_gap(self.run)

    def after(self, kind):
        self.outbound.append(("after", kind))


class FakeRun(object):
    """Stands in for N.Connect: the modal and the profile as plain values, and
    a record of every control pressed."""

    def __init__(self, before=None, after=None, modal_text=FIRST, buttons=None,
                 blocked=None, limit=300):
        self.slug = SLUG
        self.name = None
        self.pace = FakePace()
        self.br = argparse.Namespace(screenshot=lambda p: None)
        self.pressed_names = []
        self.pressed = False
        self.blocked = list(blocked or [])
        self.limit = limit
        self.reads = [before or ("Jane Example", "2nd", (True, "on the card", "topcard", URL,
                                                          False)),
                      after or ("Jane Example", "2nd", (True, "on the card", "topcard", URL,
                                                         False))]
        self.open_state = {"modals": 1, "text": modal_text, "value": None, "counters": [],
                           "buttons": [{"name": n, "disabled": False} for n in (
                               buttons or [S.INVITE_DISMISS, S.INVITE_ADD_NOTE,
                                           S.INVITE_SEND_BARE])]}
        self.note = None
        self.dismissed = 0
        self.page = argparse.Namespace(url=URL)
        self.after_gap = None      # a function applied to the run when pace.before runs
        self.pace.run = self

    def profile(self, why):
        return self.reads.pop(0)

    def arm(self):
        pass

    def disarm(self):
        pass

    def wait(self, s):
        pass

    def open_invitation(self, url):
        return dict(self.open_state)

    def modal(self):
        st = dict(self.open_state)
        st["value"] = self.note
        if self.dismissed or self.pressed:
            st["modals"] = 0
        return st

    def dismiss(self):
        self.dismissed += 1

    def type_note(self, note):
        if N.page_length(note) > self.limit:
            raise N.Refused("the note is too long")
        self.note = note
        return self.limit, self.modal()

    def prove_unchanged(self, via):
        return N.Connect.prove_unchanged(self, via)

    def button(self, name):
        run = self

        class Btn(object):
            def click(self, timeout=None):
                run.pressed_names.append(name)
        return Btn()


def drive(run, **kw):
    a = args(**kw)
    note = kw.get("note")
    expect = kw.get("expect_name")
    buf = io.StringIO()
    code = 0
    with redirect_stdout(buf):
        try:
            N._connect(a, run, note, expect, 0)
        except SystemExit as exc:
            code = exc.code
    return code, buf.getvalue()


SENDS = (S.INVITE_SEND_BARE, S.INVITE_SEND_NOTE)


class Staged(unittest.TestCase):

    def test_staged_presses_no_send_and_reserves_no_slot(self):
        run = FakeRun()
        code, out = drive(run, note="Glad to connect.")
        self.assertEqual(code, 0, out)
        self.assertIn("RESULT connect staged", out)
        self.assertEqual([n for n in run.pressed_names if n in SENDS], [])
        self.assertEqual(run.pace.outbound, [])
        self.assertEqual(run.dismissed, 1)

    def test_pending_after_a_staged_run_fails_loudly(self):
        after = ("Jane Example", "2nd", (False, "PENDING", None, None, True))
        code, out = drive(FakeRun(after=after))
        self.assertEqual(code, 1)
        self.assertIn("PENDING", out)
        self.assertNotIn("RESULT connect staged", out)

    def test_an_invite_that_moved_is_not_a_surviving_state(self):
        after = ("Jane Example", "2nd", (True, "in the menu", "more-menu", URL, False))
        code, out = drive(FakeRun(after=after))
        self.assertEqual(code, 1)
        self.assertIn("did not survive", out)

    def test_a_blocked_invitation_request_fails_a_staged_run(self):
        code, out = drive(FakeRun(blocked=["https://www.linkedin.com/x/invitations"]))
        self.assertEqual(code, 1)
        self.assertIn("BLOCKED", out)

    def test_a_modal_naming_someone_else_is_dismissed_and_fails(self):
        run = FakeRun(modal_text=FIRST.replace("Jane Example", "John Other"))
        code, out = drive(run)
        self.assertEqual(code, 1)
        self.assertEqual(run.dismissed, 1)
        self.assertEqual(run.pressed_names, [])

    def test_an_unmeasured_modal_is_dismissed_and_fails(self):
        run = FakeRun(buttons=[S.INVITE_DISMISS, "Verify email", S.INVITE_SEND_BARE])
        code, out = drive(run)
        self.assertEqual(code, 1)
        self.assertIn("not the", out)
        self.assertEqual(run.dismissed, 1)

    def test_a_note_over_the_limit_refuses_and_still_proves_the_state(self):
        run = FakeRun(limit=10)
        code, out = drive(run, note="this note is longer than ten")
        self.assertEqual(code, 1)
        self.assertIn("RESULT connect refused", out)
        self.assertIn("modal=dismissed-and-proven", out)
        self.assertEqual(run.reads, [])      # the proving reload was taken

    def test_a_wrong_greeting_refuses_before_the_modal(self):
        run = FakeRun()
        code, out = drive(run, note="Hi Robert, glad to connect.")
        self.assertEqual(code, 1)
        self.assertIn("refused", out)
        self.assertEqual(run.dismissed, 0)

    def test_already_pending_opens_nothing(self):
        before = ("Jane Example", "2nd", (False, "PENDING", None, None, True))
        run = FakeRun(before=before)
        code, out = drive(run)
        self.assertEqual(code, 0)
        self.assertIn("RESULT connect already-pending", out)
        self.assertEqual(run.dismissed, 0)


class Submitted(unittest.TestCase):

    def test_with_a_note_it_presses_send_invitation_and_proves_pending(self):
        after = ("Jane Example", "2nd", (False, "PENDING", None, None, True))
        run = FakeRun(after=after)
        code, out = drive(run, note="Glad to connect.", submit=True, expect_name="Jane Example")
        self.assertEqual(code, 0, out)
        self.assertEqual(run.pressed_names, [S.INVITE_SEND_NOTE])
        self.assertEqual(run.pace.outbound, [("before", "connect"), ("after", "connect")])
        self.assertIn("RESULT connect sent", out)

    def test_without_a_note_it_presses_send_without_a_note(self):
        after = ("Jane Example", "2nd", (False, "PENDING", None, None, True))
        run = FakeRun(after=after)
        code, out = drive(run, submit=True, expect_name="Jane Example")
        self.assertEqual(code, 0, out)
        self.assertEqual(run.pressed_names, [S.INVITE_SEND_BARE])

    def test_no_pending_after_the_press_is_a_fail_that_says_it_may_have_gone(self):
        run = FakeRun()
        code, out = drive(run, submit=True, expect_name="Jane Example")
        self.assertEqual(code, 1)
        self.assertIn("MAY have gone", out)
        self.assertNotIn("RESULT connect sent", out)

    def assert_nothing_pressed(self, run, code, out):
        self.assertEqual(code, 1, out)
        self.assertEqual(run.pressed_names, [])
        self.assertNotIn("RESULT connect sent", out)

    def test_a_modal_gone_after_the_gap_presses_nothing(self):
        run = FakeRun()
        run.after_gap = lambda r: r.open_state.update(modals=0)
        code, out = drive(run, submit=True, expect_name="Jane Example")
        self.assert_nothing_pressed(run, code, out)

    def test_a_note_changed_during_the_gap_presses_nothing(self):
        run = FakeRun()
        run.after_gap = lambda r: setattr(r, "note", "something else")
        code, out = drive(run, note="Glad to connect.", submit=True, expect_name="Jane Example")
        self.assert_nothing_pressed(run, code, out)

    def test_a_blocked_request_before_send_presses_nothing(self):
        run = FakeRun(blocked=["https://www.linkedin.com/x/invitations"])
        code, out = drive(run, submit=True, expect_name="Jane Example")
        self.assert_nothing_pressed(run, code, out)

    def test_a_tab_moved_to_another_persons_invitation_presses_nothing(self):
        # Review finding 1: the browser is shared, and the gap is up to 90 s.
        run = FakeRun()
        run.after_gap = lambda r: setattr(r.page, "url", URL.replace("jane-example", "john-other"))
        code, out = drive(run, submit=True, expect_name="Jane Example")
        self.assert_nothing_pressed(run, code, out)

    def test_a_modal_naming_someone_else_after_the_gap_presses_nothing(self):
        run = FakeRun()
        run.after_gap = lambda r: r.open_state.update(
            text=FIRST.replace("Jane Example", "John Other"))
        code, out = drive(run, submit=True, expect_name="Jane Example")
        self.assert_nothing_pressed(run, code, out)

    def test_a_wrong_expect_name_refuses_before_the_modal(self):
        run = FakeRun()
        code, out = drive(run, submit=True, expect_name="Joanne Example")
        self.assertEqual(code, 1)
        self.assertIn("RESULT connect refused", out)
        self.assertEqual(run.pressed_names, [])
        self.assertEqual(run.dismissed, 0)


def code_only(src):
    """The source with every comment and string literal removed, so a check
    reads what the code DOES and not what its prose says about it - the prose
    here names the very calls it forbids."""
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        out.append(tok.string)
    return " ".join(out)


class Source(unittest.TestCase):
    """Properties of the code itself."""

    def connect_source(self):
        path = os.path.join(os.path.dirname(N.__file__), "connections.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        return code_only(src[src.index("# `connect`: send ONE invitation"):])

    def test_no_key_is_pressed_anywhere_in_connect(self):
        src = self.connect_source()
        for call in (r"\. press \(", r"\. type \(", r"press_sequentially", r"type_text",
                     r"keyboard \. down", r"keyboard \. up"):
            self.assertNotRegex(src, call)
        # and the one typing call there is, is there - so this is not a check
        # that passes on a file it failed to read
        self.assertRegex(src, r"keyboard \. insert_text")

    def test_the_cards_control_is_never_clicked(self):
        # Pressing it fires the SDUI post-connect request (measured 2026-10-20).
        src = self.connect_source()
        self.assertNotRegex(src, r"INVITE_HREF|INVITE_ARIA")

    def test_the_guard_is_never_unrouted(self):
        self.assertNotRegex(self.connect_source(), r"\. unroute \(")

    def test_the_selftest_never_submits(self):
        path = os.path.join(os.path.dirname(N.__file__), "selftest.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        # The Phase 3 block, which is where the reach verbs are run. Phase 1
        # legitimately publishes a throwaway post to OUR OWN PAGE with
        # submit=True; that reaches no person and is not this check's business.
        start = src.index("PHASE 3: connect, STAGED")
        block = src[start:src.index("-- P2-9:", start)]
        self.assertIn("N.connect", block)
        self.assertNotRegex(code_only(block), r"submit = True|\] = True|: True")
        # every call of the verb goes through stage(), which forces submit off
        self.assertEqual(len(re.findall(r"N\.connect", block)), 1)
        self.assertIn("return attempt(name, N.connect, **args)", block)
        self.assertIn('args["submit"] = False', block)


if __name__ == "__main__":
    unittest.main()
