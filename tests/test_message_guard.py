# -*- coding: utf-8 -*-
"""Design rule 0.2, and everything either side of it, driven with a stub browser
so no page opens and nothing reaches anybody.

THE RULE, RESTATED BECAUSE IT IS THE ONE THAT CAN HURT A REAL PERSON. On
LinkedIn's message box, Enter SENDS. `Browser.type_text` - which every Phase 1
verb uses - presses Enter once per newline, so a three-paragraph draft typed
with it sends three fragments to a real person and nothing takes them back.

So `kit/messaging.py` has its own typing path, and these tests hold it to three
separate promises:

  1. IT NEVER PRESSES A BARE ENTER. Every keyboard event the typing path emits
     is recorded, and the test asserts on the whole list - not that Enter is
     rare, that it never occurs. A test that only checked the bubble count would
     pass on a path that pressed Enter into an account whose setting happens to
     be "Click Send", and would then ship to an account whose setting is not.
  2. THE COUNT IS WHAT PROVES IT, not the care. The stub can be told to grow the
     thread mid-draft, which is what a fragment going out looks like from here,
     and the verb must fail saying exactly that.
  3. IT STOPS AT THE FIRST FRAGMENT. A three-line draft that has started sending
     must send one fragment and not three, so the test counts the lines that
     were typed after the thread grew.

WHAT THESE CANNOT PROVE, said plainly: they do not prove that Shift+Enter fails
to submit LinkedIn's form, and they do not prove Input.insertText fires no key
events - those are facts about Chrome and about LinkedIn's page, and the second
was measured while the first is a convention this code relies on. What is proven
here is that the tool does what it says either side of them, and that the guard
which would catch either being wrong actually fires.
"""
import argparse
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit import browser as B
from kit import messaging as M
from kit import selectors as S

THREAD = "https://www.linkedin.com/messaging/thread/2-abcdef/"


def bubble(sender, text, when="1:00 PM"):
    return {"sender": sender, "sender_stated_here": True, "text": text, "when": when}


class Keyboard(object):
    """Every keystroke and every insertion, in order. The whole point of this
    class is that the test can assert on what was NOT pressed."""

    def __init__(self, page):
        self.page = page
        self.events = []

    def press(self, key):
        self.events.append(("press", key))
        if key == "Control+A":
            self.page.selected = True
        elif key == "Delete" and self.page.selected:
            self.page.composer_text = ""
            self.page.selected = False
        elif key == "Shift+Enter":
            self.page.composer_text += "\n"
            self.page.lines_typed += 0
        elif key == "Enter":
            # WHAT A BARE ENTER DOES ON THE LIVE PAGE. The stub models it so
            # that a regression which reintroduced it is caught by the same
            # count the live guard uses, and not only by the assertion on the
            # event list.
            self.page.messages = self.page.messages + [bubble("Us", self.page.composer_text)]
            self.page.composer_text = ""

    def insert_text(self, text):
        self.events.append(("insert", text))
        self.page.composer_text += text
        self.page.lines_typed += 1
        if self.page.grow_after is not None and self.page.lines_typed >= self.page.grow_after:
            self.page.messages = self.page.messages + [bubble("Us", "a fragment")]
            self.page.grow_after = None


class StubLocator(object):

    def __init__(self, page, n, kind=None, disabled=False, text="", href=None):
        self.page, self.n, self.kind = page, n, kind
        self._disabled, self._text, self._href = disabled, text, href
        self.first = self

    def count(self):
        return self.n

    def nth(self, i):
        return self

    def locator(self, sel):
        return self.page.locator(sel)

    def focus(self):
        if self.kind == "composer":
            self.page.focused = True

    def click(self, timeout=None):
        if self.kind == "send":
            self.page.sent = self.page.composer_text
            self.page.messages = self.page.messages + [bubble("Us", self.page.composer_text)]
            self.page.composer_text = ""
        elif self.kind == "row":
            self.page.opened_row = True

    def is_disabled(self):
        return self._disabled

    def is_visible(self):
        return True

    def inner_text(self):
        return self._text

    def get_attribute(self, name):
        return self._href if name == "href" else None


class StubPage(object):

    def __init__(self, messages, rows=None, header=("A Person", "/in/aperson/"),
                 send_count=1, composer_count=1, composer_text="",
                 grow_after=None, url=THREAD, message_href=THREAD):
        self.messages = list(messages)
        self.rows = list(rows or [])
        self.header = header
        self.send_count = send_count
        self.composer_count = composer_count
        self.composer_text = composer_text
        self.grow_after = grow_after
        self.url = url
        self.message_href = message_href
        self.keyboard = Keyboard(self)
        self.focused = False
        self.selected = False
        self.sent = None
        self.lines_typed = 0
        self.opened_row = False
        self.thread_open_on_list = 0

    # -- what the module reads ---------------------------------------------
    def evaluate(self, js, arg=None):
        if js is M.MESSAGES_JS:
            return [dict(m) for m in self.messages]
        if js is M.ROWS_JS:
            return [dict(r) for r in self.rows]
        if js is M.THREAD_OPEN_JS:
            return {"events": self.thread_open_on_list,
                    "quickReplies": 0, "titleBar": self.thread_open_on_list}
        if isinstance(js, str) and "querySelectorAll('a[href*=\"/messaging/\"]')" in js:
            # The profile route: the Message control's href, taken off the
            # profile rather than assembled, because it carries a urn this code
            # has no other way to know.
            return self.message_href
        if js is M.COMPOSER_JS:
            box = self.composer_text
            # An EMPTY composer holds one character on the live page, not zero.
            n = len(box) if box else S.COMPOSER_EMPTY_LEN
            return {"present": self.composer_count > 0, "text": box, "len": n,
                    "focused": self.focused, "focusInside": self.focused,
                    "sendPresent": self.send_count > 0,
                    "sendDisabled": not box, "sendType": "submit", "sendInForm": True}
        return None

    def locator(self, sel):
        if sel == S.COMPOSER:
            return StubLocator(self, self.composer_count, kind="composer")
        if sel == S.COMPOSER_SEND:
            return StubLocator(self, self.send_count, kind="send",
                               disabled=not self.composer_text)
        if sel == S.THREAD_EVENT:
            return StubLocator(self, len(self.messages))
        if sel == S.QUICK_REPLIES:
            return StubLocator(self, 1)
        if sel == S.THREAD_HEADER_LINK:
            return StubLocator(self, 1, text=self.header[0], href=self.header[1])
        if sel == S.CONVO_CARD:
            return StubLocator(self, len(self.rows), kind="row")
        if sel == S.INBOX_UNREAD_PILL:
            return StubLocator(self, 1)
        return StubLocator(self, 0)

    def get_by_role(self, role, name=None):
        return StubLocator(self, 0)


class StubBrowser(object):

    def __init__(self, page):
        self.page = page
        self.presses = []

    def __call__(self, port):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, url, where, settle=6):
        self.page.url = url
        return url

    def press(self, locator, what):
        self.presses.append(what)


class MessagingCase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cc-linkedin-msg-")
        self._state, B.STATE_DIR = B.STATE_DIR, self.dir
        self._vgap, B.Pace.VIEW_GAP = B.Pace.VIEW_GAP, (0, 0)
        self._ogap, B.Pace.GAP = B.Pace.GAP, (0, 0)
        self._browser, M.Browser = M.Browser, None
        self._ls, M.LIST_SETTLE = M.LIST_SETTLE, 0
        self._ts, M.THREAD_SETTLE = M.THREAD_SETTLE, 0
        self._tys, M.TYPE_SETTLE = M.TYPE_SETTLE, 0
        del B._VIEWS[:]

    def tearDown(self):
        B.STATE_DIR = self._state
        B.Pace.VIEW_GAP = self._vgap
        B.Pace.GAP = self._ogap
        M.Browser = self._browser
        M.LIST_SETTLE = self._ls
        M.THREAD_SETTLE = self._ts
        M.TYPE_SETTLE = self._tys
        del B._VIEWS[:]
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_verb(self, fn, page, **kw):
        br = StubBrowser(page)
        M.Browser = br
        self.browser, self.page = br, page
        args = dict(url=THREAD, text="hello", text_file=None, expect_name=None,
                    submit=False, dump=None, port=9224, limit=25, unread=False)
        args.update(kw)
        out = io.StringIO()
        stdout, sys.stdout = sys.stdout, out
        try:
            fn(argparse.Namespace(**args))
        except SystemExit as exc:
            return exc.code
        finally:
            sys.stdout = stdout
            self.said = out.getvalue()
        return None


# ------------------------------------------------------- rule 0.2, the typing

class TheComposerNeverPressesEnter(MessagingCase):

    def test_a_three_paragraph_draft_presses_shift_enter_and_never_enter(self):
        """P3-7. The line breaks arrive AND the guard is watched NOT firing when
        the code is correct - a guard only ever seen firing is not known to be
        quiet at the right times."""
        page = StubPage([bubble("Them", "hi")])
        code = self.run_verb(M.message, page, text="one\n\ntwo\n\nthree")
        self.assertIsNone(code, self.said)
        keys = [k for kind, k in page.keyboard.events if kind == "press"]
        self.assertNotIn("Enter", keys,
                         "a BARE ENTER was pressed into the message composer: %s" % keys)
        self.assertEqual(keys.count("Shift+Enter"), 4, keys)
        inserted = [t for kind, t in page.keyboard.events if kind == "insert"]
        self.assertEqual(inserted, ["one", "two", "three"])

    def test_the_typed_draft_is_read_back_before_anything_else_happens(self):
        page = StubPage([bubble("Them", "hi")])
        self.run_verb(M.message, page, text="line one\nline two")
        self.assertIn("unchanged=true", self.said)

    def test_a_draft_that_does_not_arrive_as_written_refuses(self):
        """The readback is a real check: a composer that swallowed a line must
        not be reported as a staged draft."""
        class Lossy(Keyboard):
            def insert_text(self, text):
                Keyboard.insert_text(self, text[:-1] if len(text) > 1 else text)
        page = StubPage([bubble("Them", "hi")])
        page.keyboard = Lossy(page)
        code = self.run_verb(M.message, page, text="hello there")
        self.assertEqual(code, 1)
        self.assertIn("did not arrive as written", self.said)


class TheBubbleCountIsTheGuard(MessagingCase):

    def test_a_fragment_going_out_mid_draft_is_a_failure_that_says_so(self):
        page = StubPage([bubble("Them", "hi")], grow_after=1)
        code = self.run_verb(M.message, page, text="one\ntwo\nthree")
        self.assertEqual(code, 1)
        self.assertIn("REACHED THE RECIPIENT", self.said)

    def test_it_stops_at_the_first_fragment_rather_than_sending_three(self):
        """The reason the count is read after EVERY line and not once at the
        end. At the end, a three-paragraph draft has already gone out as three
        separate messages and the report is an obituary."""
        page = StubPage([bubble("Them", "hi")], grow_after=1)
        self.run_verb(M.message, page, text="one\ntwo\nthree")
        self.assertEqual(page.lines_typed, 1,
                         "typing continued after the thread grew: %d lines went in"
                         % page.lines_typed)

    def test_a_quiet_thread_is_not_reported_as_a_fragment(self):
        """The negative control for the check above."""
        page = StubPage([bubble("Them", "hi")], grow_after=None)
        self.assertIsNone(self.run_verb(M.message, page, text="one\ntwo\nthree"), self.said)


# ------------------------------------------------------ rule 0.1, the staging

class AStagedRunProvesNothingHappened(MessagingCase):

    def test_the_happy_path_says_the_thread_is_unchanged_and_the_draft_is_gone(self):
        page = StubPage([bubble("Them", "hi"), bubble("Us", "hello")])
        self.assertIsNone(self.run_verb(M.message, page, text="a draft"), self.said)
        self.assertIn("RESULT message-staged", self.said)
        self.assertIn("draft_cleared=true", self.said)
        self.assertEqual(page.composer_text, "")

    def test_a_draft_that_survives_the_reload_is_a_failure(self):
        """LinkedIn keeps message drafts. A staged run that left one behind has
        not left the surface as it found it, and the next run would type into
        it."""
        page = StubPage([bubble("Them", "hi")])

        class Sticky(Keyboard):
            def press(self, key):
                if key == "Delete":
                    self.events.append(("press", key))
                    return          # the draft survives
                Keyboard.press(self, key)
        page.keyboard = Sticky(page)
        code = self.run_verb(M.message, page, text="a draft")
        self.assertEqual(code, 1)
        self.assertIn("still in the composer", self.said)

    def test_a_thread_that_grew_between_typing_and_the_reload_is_a_failure(self):
        page = StubPage([bubble("Them", "hi")])
        real = M._clear_composer

        def grow(br):
            got = real(br)
            br.page.messages = br.page.messages + [bubble("Them", "and another")]
            return got
        M._clear_composer = grow
        try:
            code = self.run_verb(M.message, page, text="a draft")
        finally:
            M._clear_composer = real
        self.assertEqual(code, 1)
        self.assertIn("did NOT survive untouched", self.said)

    def test_a_composer_that_already_holds_a_draft_refuses_before_typing(self):
        page = StubPage([bubble("Them", "hi")], composer_text="somebody else's half sentence")
        code = self.run_verb(M.message, page, text="mine")
        self.assertEqual(code, 1)
        self.assertIn("a draft this run did not write", self.said)
        self.assertEqual(page.lines_typed, 0)


# --------------------------------------------------- rule 0.3, naming the target

class AnIrreversibleActNamesItsTargetTwice(MessagingCase):

    def test_submit_without_expect_name_refuses(self):
        page = StubPage([bubble("Them", "hi")])
        code = self.run_verb(M.message, page, submit=True, expect_name=None)
        self.assertEqual(code, 1)
        self.assertIn("--expect-name is REQUIRED", self.said)
        self.assertEqual(page.lines_typed, 0)

    def test_a_mismatched_name_refuses_before_anything_is_typed(self):
        page = StubPage([bubble("Them", "hi")], header=("A Person", "/in/aperson/"))
        code = self.run_verb(M.message, page, submit=True, expect_name="Somebody Else")
        self.assertEqual(code, 1)
        self.assertIn("two different people", self.said)
        self.assertEqual(page.lines_typed, 0)
        self.assertIsNone(page.sent)

    def test_a_thread_with_the_wrong_person_refuses_even_when_the_name_matches(self):
        """The slug is the second reading off the same control, and it catches
        what a display name cannot: the profile route resolves a conversation
        through an href taken off the page, and an href that leads to somebody
        else's thread is a wrong answer a matching name would wave through."""
        page = StubPage([bubble("Them", "hi")], header=("A Person", "/in/someone-else/"))
        code = self.run_verb(M.message, page,
                             url="https://www.linkedin.com/in/aperson/",
                             expect_name="A Person")
        self.assertEqual(code, 1)
        self.assertIn("was asked for", self.said)
        self.assertEqual(page.lines_typed, 0)

    def test_the_profile_route_goes_ahead_when_the_slug_agrees(self):
        """The negative control: the same path with the conversation the profile
        actually names."""
        page = StubPage([bubble("Them", "hi")], header=("A Person", "/in/aperson/"))
        self.assertIsNone(self.run_verb(M.message, page,
                                        url="https://www.linkedin.com/in/aperson/",
                                        expect_name="A Person"), self.said)

    def test_a_matching_name_and_slug_goes_ahead(self):
        page = StubPage([bubble("Them", "hi")], header=("A Person", "/in/aperson/"),
                        url=THREAD)
        self.assertIsNone(self.run_verb(M.message, page, expect_name="A Person"), self.said)


class SendIsIdentifiedPositively(MessagingCase):

    def test_two_send_buttons_is_a_refusal_and_not_a_choice(self):
        page = StubPage([bubble("Them", "hi")], send_count=2)
        code = self.run_verb(M.message, page, submit=True, expect_name="A Person")
        self.assertEqual(code, 1)
        self.assertIn("NOTHING WAS SENT", self.said)
        self.assertIsNone(page.sent)

    def test_two_composers_is_a_refusal_before_a_key_is_pressed(self):
        page = StubPage([bubble("Them", "hi")], composer_count=2)
        code = self.run_verb(M.message, page)
        self.assertEqual(code, 1)
        self.assertIn("will not type into a page", self.said)
        self.assertEqual(page.keyboard.events, [])


# ------------------------------------------------------------------ read-inbox

def row(i, who, when="1:00 PM", unread=False, snippet="a line"):
    return {"index": i, "participant": who, "last_line": snippet, "when": when,
            "when_datetime": None, "unread_class": unread,
            "unread_count_label": ("1 unread message" if unread else None), "href": None}


class ReadInboxOpensNothing(MessagingCase):

    def test_it_returns_a_row_per_conversation_with_a_thread_ref(self):
        page = StubPage([], rows=[row(0, "A Person", unread=True), row(1, "Another")])
        self.assertIsNone(self.run_verb(M.read_inbox, page), self.said)
        self.assertIn("RESULT read-inbox rows=2", self.said)
        self.assertIn(M.REF_PREFIX, self.said)
        self.assertIn("opened_nothing=true", self.said)

    def test_a_thread_open_on_the_list_is_a_failure_that_says_what_it_cost(self):
        """The route was measured to select nothing. If that ever changes, a run
        has already marked somebody's conversation read - so it goes red rather
        than doing it quietly on every listing."""
        page = StubPage([], rows=[row(0, "A Person")])
        page.thread_open_on_list = 4
        code = self.run_verb(M.read_inbox, page)
        self.assertEqual(code, 1)
        self.assertIn("ALREADY MARKED SOMEBODY'S CONVERSATION READ", self.said)

    def test_zero_rows_is_a_failure(self):
        page = StubPage([], rows=[])
        code = self.run_verb(M.read_inbox, page)
        self.assertEqual(code, 1)
        self.assertIn("broken selector", self.said)

    def test_the_two_unread_signals_disagreeing_is_a_failure(self):
        """A renamed class token would otherwise report an inbox that quietly
        has nothing unread."""
        bad = row(0, "A Person", unread=False)
        bad["unread_count_label"] = "2 unread messages"
        page = StubPage([], rows=[bad, row(1, "Another")])
        code = self.run_verb(M.read_inbox, page)
        self.assertEqual(code, 1)
        self.assertIn("disagree with themselves", self.said)

    def test_an_all_read_inbox_says_it_could_not_confirm_the_marker(self):
        """An inbox with nothing unread is ordinary, so this is not a failure -
        but it must never read as a confident 'nothing unread'."""
        page = StubPage([], rows=[row(0, "A Person"), row(1, "Another")])
        self.assertIsNone(self.run_verb(M.read_inbox, page), self.said)
        self.assertIn("could not confirm the marker", self.said)

    def test_a_row_with_no_snippet_is_kept(self):
        """Two rows of ten carried no snippet. A parser that required all three
        fields would drop a fifth of the inbox and call the rest complete."""
        page = StubPage([], rows=[row(0, "A Person", snippet=None), row(1, "Another")])
        self.assertIsNone(self.run_verb(M.read_inbox, page), self.said)
        self.assertIn("rows=2", self.said)


class ThreadReferences(MessagingCase):

    def test_a_reference_round_trips_to_the_row_it_names(self):
        r = row(3, "A Person", when="2:15 PM")
        ref = M.make_ref(r, "FOCUSED")
        self.assertTrue(M.is_ref(ref))
        got = M.parse_ref(ref)
        self.assertEqual(got["who"], "A Person")
        self.assertEqual(got["when"], "2:15 PM")

    def test_two_rows_matching_one_reference_is_ambiguity_with_no_outcome(self):
        page = StubPage([bubble("Them", "hi")],
                        rows=[row(0, "A Person", when="1:00 PM"),
                              row(1, "A Person", when="1:00 PM")])
        ref = M.make_ref(row(0, "A Person", when="1:00 PM"), "FOCUSED")
        code = self.run_verb(M.read_thread, page, url=ref)
        self.assertEqual(code, 1)
        self.assertIn("Ambiguity has no outcome", self.said)
        self.assertFalse(page.opened_row)

    def test_a_reference_naming_nobody_on_the_list_refuses(self):
        page = StubPage([bubble("Them", "hi")], rows=[row(0, "Someone Else")])
        ref = M.make_ref(row(0, "A Person"), "FOCUSED")
        code = self.run_verb(M.read_thread, page, url=ref)
        self.assertEqual(code, 1)
        self.assertIn("no conversation on this list matches", self.said)

    def test_a_string_that_is_not_a_reference_is_refused_by_read_thread(self):
        page = StubPage([bubble("Them", "hi")])
        code = self.run_verb(M.read_thread, page, url="https://www.linkedin.com/feed/")
        self.assertEqual(code, 1)
        self.assertIn("is neither", self.said)


class ReadThreadSaysWhatItCost(MessagingCase):

    def test_the_result_line_carries_marked_read(self):
        page = StubPage([bubble("Them", "hi"), bubble("Us", "hello")])
        self.assertIsNone(self.run_verb(M.read_thread, page, url=THREAD), self.said)
        self.assertIn("marked_read=true", self.said)

    def test_an_empty_thread_is_a_failure(self):
        page = StubPage([])
        code = self.run_verb(M.read_thread, page, url=THREAD)
        self.assertEqual(code, 1)
        self.assertIn("broken selector", self.said)

    def test_it_reports_the_quick_reply_row_it_did_not_touch(self):
        page = StubPage([bubble("Them", "hi")])
        self.run_verb(M.read_thread, page, url=THREAD)
        self.assertIn("quick_reply_rows=1", self.said)


class AThreadIsCappedAndTheListIsToo(MessagingCase):
    """A2, as it stands. Both messaging reads are on the CAPPED counter today -
    the thread deliberately, because opening one marks it read; the list only
    because the safe route to it is the compose URL, which A2 did not uncap. The
    report asks the Architect about the second half; this records what the code
    does today so a change to it cannot be silent."""

    def test_reading_the_inbox_spends_a_capped_view(self):
        page = StubPage([], rows=[row(0, "A Person")])
        self.run_verb(M.read_inbox, page)
        self.assertEqual(len(B.views_taken("view")), 1)
        self.assertEqual(len(B.views_taken("view_self")), 0)

    def test_reading_a_thread_spends_a_capped_view(self):
        page = StubPage([bubble("Them", "hi")])
        self.run_verb(M.read_thread, page, url=THREAD)
        self.assertEqual(len(B.views_taken("view")), 1)


if __name__ == "__main__":
    unittest.main()
