# -*- coding: utf-8 -*-
"""The guards on `connect`, `invitations`, `follow`/`unfollow` and
`invite-to-follow`, driven with a stub browser so no page opens, no invitation
is sent, no Page is followed and no credit is spent.

WHAT IS BEING GUARDED, AND WHY EACH ONE IS HERE.

  * `connect` is the second irreversible verb this toolkit has, and it is worse
    than the first: withdrawing an invitation costs the other person up to three
    weeks before they can be invited again, so a mistaken invitation cannot even
    be tidied away for free. Rule 0.3 makes it name its target twice, and rule
    0.1 makes a STAGED run prove the pre-action state survived - on two
    independent surfaces, because "we did not send it" is a claim of absence and
    an absence certifies itself.
  * THE NOTE LIMIT IS READ OFF THE PAGE. Design 4.1 said 200 and the page says
    300, and the textarea carries no maxlength - the browser enforces nothing.
    A verb that fell back on a remembered number would be wrong today, so the
    absence of a stated limit is a refusal and not a default.
  * `invitations` carries the ONE exception to the zero-rows rule in this
    toolkit, and A4 narrowed it: the exception is earned by the page publishing
    a count, the count is a PER-FILTER PILL, and a pill that cannot be read
    takes the exception away rather than licensing the parse.
  * `follow` reads THREE independent signals for one state and refuses when they
    disagree. The state decides whether the control gets pressed at all, so a
    misread is a Page followed or unfollowed on somebody's behalf.
  * `invite-to-follow` proves itself on the CREDIT COUNT and not on a row that
    says "Invited". The credit is the thing that is actually spent.

WHAT THESE CANNOT PROVE: none of them proves that pressing anything works. That
is a live-page fact, and for `connect` and `message` it is deliberately still
unproven - see docs/phase-3-report.md. What is proven here is everything either
side of the press, and that every refusal fires for its own reason.
"""
import argparse
import io
import re
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit import browser as B
from kit import connections as N
from kit import people as P
from kit import selectors as S

PROFILE = "https://www.linkedin.com/in/target/"
INVITE_URL = "https://www.linkedin.com/preload/custom-invite/?vanityName=target"

LANDING = ("Dialog content start. Add a note to your invitation? Personalize your "
           "invitation to A Person by adding a note. LinkedIn members are more likely "
           "to accept invitations that include a note. Add a note Send without a note")
NOTE_OPEN = ("Dialog content start. Add a note to your invitation Please limit personal "
             "note to 300 characters. LinkedIn members are more likely to accept "
             "invitations that include a personal note. 0/300 Cancel Send")


def dialog(text, labelledby=S.INVITE_MODAL_LABELLEDBY):
    return {"tag": "DIV", "role": "dialog", "labelledby": labelledby, "label": None,
            "text": text, "buttons": []}


class StubLocator(object):

    def __init__(self, page, n, kind=None, disabled=False):
        self.page, self.n, self.kind, self._disabled = page, n, kind, disabled
        self.first = self

    def count(self):
        return self.n

    def nth(self, i):
        return self

    def locator(self, sel):
        return self.page.locator(sel)

    def focus(self):
        pass

    def fill(self, v):
        pass

    def type(self, v, delay=None):
        pass

    def is_disabled(self):
        return self._disabled

    def is_visible(self):
        return True

    def click(self, timeout=None):
        self.page.clicked.append(self.kind)
        if self.kind == "add-note":
            self.page.note_open = True
        elif self.kind == "send-invite":
            self.page.sent = True
        elif self.kind == "invite-submit":
            self.page.invited = True
        elif self.kind == "select":
            self.page.checked += 1
        elif self.kind == "dismiss":
            self.page.note_open = False


class StubKeyboard(object):

    def __init__(self, page):
        self.page = page
        self.events = []

    def press(self, key):
        self.events.append(key)

    def insert_text(self, text):
        self.events.append(("insert", text))
        self.page.note_value += text


class StubPage(object):
    """One page object standing in for whichever Phase 3 surface a test needs."""

    def __init__(self, **kw):
        self.url = kw.get("url", INVITE_URL)
        self.keyboard = StubKeyboard(self)
        self.clicked = []
        self.note_open = False
        self.note_value = ""
        self.note_lost = kw.get("note_lost", 0)
        self.counter_says = kw.get("counter_says")
        self.landing_text = kw.get("landing_text", LANDING)
        self.note_text = kw.get("note_text", NOTE_OPEN)
        self.labelledby = kw.get("labelledby", S.INVITE_MODAL_LABELLEDBY)
        self.sent = False
        self.invited = False
        self.add_note_count = kw.get("add_note_count", 1)
        self.send_count = kw.get("send_count", 1)
        # received invitations
        self.received = kw.get("received", [])
        self.body = kw.get("body", "")
        self.radios = kw.get("radios", [])
        # follow
        self.follow = kw.get("follow")
        # invite dialog
        self.invite = kw.get("invite")
        self.checked = 0
        self.select_count = kw.get("select_count", 1)

    def evaluate(self, js, arg=None):
        if js is N.ANY_DIALOG_JS:
            text = self.note_text if self.note_open else self.landing_text
            if self.note_open:
                # The page publishes a LIVE counter beside the box. The stub
                # moves it the way the page does - whatever limit the note text
                # states - so a test can point the two readings at each other.
                shown = (self.counter_says if self.counter_says is not None
                         else len(self.note_value))
                text = re.sub(r"\b0\s*/\s*(\d+)", lambda m: "%d/%s" % (shown, m.group(1)),
                              text, count=1)
            return [dialog(text, self.labelledby)]
        if js is N.NOTE_BOX_JS:
            v = self.note_value[:len(self.note_value) - self.note_lost] \
                if self.note_lost else self.note_value
            return {"value": v, "len": len(v), "maxlength": None, "focused": True}
        if js is N.RECEIVED_ROWS_JS:
            return [dict(r) for r in self.received]
        if js is N.FILTERS_JS:
            return [dict(r) for r in self.radios]
        if js is N.FOLLOW_JS:
            return self.follow
        if js is N.PAGE_INVITE_JS:
            got = dict(self.invite)
            got["checked"] = self.checked
            return got
        if isinstance(js, str) and "document.body" in js:
            return self.body
        return None

    def locator(self, sel):
        if sel == S.NOTE_BOX:
            return StubLocator(self, 1)
        if sel == S.COMPANY_TOP_CARD:
            return StubLocator(self, 1)
        if sel == S.FOLLOW_BUTTON:
            return StubLocator(self, 1, kind="follow")
        if sel == S.PAGE_INVITE_DIALOG:
            return StubLocator(self, 1)
        if sel == S.PAGE_INVITE_SEARCH:
            return StubLocator(self, 1)
        return StubLocator(self, 0)

    def get_by_role(self, role, name=None):
        # The verb builds its patterns with re.escape, which turns a space into
        # "\ ". The stub matches on the words a person would read, so it has to
        # undo that rather than compare against an escaped string.
        raw = getattr(name, "pattern", str(name))
        pat = raw.replace("\\", "")
        if S.INVITE_ADD_NOTE.lower() in pat.lower():
            return StubLocator(self, self.add_note_count, kind="add-note")
        if "Send invitation" in pat or "Send without a note" in pat:
            return StubLocator(self, self.send_count, kind="send-invite",
                               disabled=self.note_open and not self.note_value)
        if S.INVITE_DISMISS.lower() in pat.lower():
            return StubLocator(self, 1, kind="dismiss")
        if raw == S.PAGE_INVITE_SUBMIT.pattern:
            return StubLocator(self, 1, kind="invite-submit",
                               disabled=self.checked == 0)
        if pat.startswith("^Select "):
            return StubLocator(self, self.select_count, kind="select")
        return StubLocator(self, 0)

    def get_by_label(self, name):
        return self.get_by_role("button", name)


class StubBrowser(object):

    def __init__(self, page, lands=None):
        self.page = page
        self.lands = lands or {}
        self.presses = []

    def __call__(self, port):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, url, where, settle=6):
        final = self.lands.get(url, url)
        self.page.url = final
        return final

    def press(self, locator, what):
        self.presses.append(what)
        self.page.clicked.append("press:%s" % what)


class Phase3Case(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cc-linkedin-p3-")
        self._state, B.STATE_DIR = B.STATE_DIR, self.dir
        self._vgap, B.Pace.VIEW_GAP = B.Pace.VIEW_GAP, (0, 0)
        self._ogap, B.Pace.GAP = B.Pace.GAP, (0, 0)
        self._browser, N.Browser = N.Browser, None
        self._act, N.ACTIVATE_SETTLE = N.ACTIVATE_SETTLE, 0
        self._resolve = P.resolve_invite
        self._sent_load = N.SentList.load
        del B._VIEWS[:]

    def tearDown(self):
        B.STATE_DIR = self._state
        B.Pace.VIEW_GAP = self._vgap
        B.Pace.GAP = self._ogap
        N.Browser = self._browser
        N.ACTIVATE_SETTLE = self._act
        P.resolve_invite = self._resolve
        N.SentList.load = self._sent_load
        del B._VIEWS[:]
        shutil.rmtree(self.dir, ignore_errors=True)

    def capture(self, fn, args):
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


# ------------------------------------------------------------------- connect

def profile(name="A Person", can=True, pending=False, url=INVITE_URL, reason="an invite control"):
    return {"slug": "target", "url": PROFILE, "name": name, "degree": "2nd",
            "primary_button": "Connect", "actions": ["Connect", "More"],
            "can_connect": can, "can_connect_reason": reason,
            "connect_via": "topcard", "connect_url": url,
            "invitation_pending": pending}


class ConnectCase(Phase3Case):

    def run_connect(self, page, profiles, sent_lists, **kw):
        """`profiles` is what resolve_invite returns on each call, in order;
        `sent_lists` is what the Sent tab holds on each load, in order."""
        seq = list(profiles)
        sent = list(sent_lists)
        taken = {"p": 0, "s": 0}

        def fake_resolve(br, pace, url):
            i = min(taken["p"], len(seq) - 1)
            taken["p"] += 1
            pace.before_view("stub profile")
            pace.after_view()
            return seq[i]

        def fake_sent(self):
            i = min(taken["s"], len(sent) - 1)
            taken["s"] += 1
            self.rows = list(sent[i])
            self.pill = len(self.rows)
            self.pace.before_self_view("stub Sent tab")
            self.pace.after_view()
            return self

        P.resolve_invite = fake_resolve
        N.SentList.load = fake_sent
        br = StubBrowser(page)
        N.Browser = br
        self.browser, self.page = br, page
        args = dict(url=PROFILE, note=None, note_file=None, expect_name=None,
                    submit=False, dump=None, port=9224)
        args.update(kw)
        return self.capture(N.connect, args)


def sent_row(slug, name="A Person"):
    return {"index": 0, "label": "Withdraw invitation sent to " + name,
            "href": "https://www.linkedin.com/", "profile": "/in/%s/" % slug,
            "age": "Sent 1 day ago"}


class AStagedConnectProvesNothingWasSent(ConnectCase):

    def test_the_happy_path_says_both_surfaces_agree(self):
        page = StubPage()
        code = self.run_connect(page, [profile(), profile()], [[]])
        self.assertIsNone(code, self.said)
        self.assertIn("RESULT connect-staged", self.said)
        self.assertIn("still_connectable=true", self.said)
        self.assertIn("not_in_sent_tab=true", self.said)
        self.assertFalse(page.sent)

    def test_a_profile_that_went_pending_is_a_failure(self):
        """The half of the proof the invitation manager cannot give: if an
        invitation really did go out, the profile says Pending."""
        page = StubPage()
        code = self.run_connect(page, [profile(), profile(can=False, pending=True)], [[]])
        self.assertEqual(code, 1)
        self.assertIn("did not survive untouched", self.said)
        self.assertIn("PENDING", self.said)

    def test_an_invitation_appearing_on_the_sent_tab_is_a_failure(self):
        """The other half, and the one design row P3-1 names."""
        page = StubPage()
        code = self.run_connect(page, [profile(), profile()], [[sent_row("target")]])
        self.assertEqual(code, 1)
        self.assertIn("now on the Sent tab", self.said)

    def test_a_staged_run_names_the_cost_of_the_failure_it_reports(self):
        page = StubPage()
        self.run_connect(page, [profile(), profile()], [[sent_row("target")]])
        self.assertIn("three weeks", self.said)


class ConnectRefusesBeforeItActs(ConnectCase):

    def test_an_invitation_already_pending_refuses_without_pressing(self):
        page = StubPage()
        code = self.run_connect(page, [profile(can=False, pending=True,
                                               reason="an invitation is already PENDING")], [[]])
        self.assertEqual(code, 1)
        self.assertIn("already outstanding", self.said)
        self.assertEqual(page.clicked, [])

    def test_a_profile_with_no_invitation_refuses(self):
        page = StubPage()
        code = self.run_connect(page, [profile(can=False, url=None,
                                               reason="no invite control anywhere")], [[]])
        self.assertEqual(code, 1)
        self.assertIn("offers no invitation to send", self.said)

    def test_submit_without_expect_name_refuses(self):
        page = StubPage()
        code = self.run_connect(page, [profile()], [[]], submit=True)
        self.assertEqual(code, 1)
        self.assertIn("--expect-name is REQUIRED", self.said)

    def test_a_name_that_does_not_match_the_profile_refuses(self):
        page = StubPage()
        code = self.run_connect(page, [profile(name="A Person")], [[]],
                                expect_name="Somebody Else")
        self.assertEqual(code, 1)
        self.assertIn("two different people", self.said)
        self.assertEqual(page.clicked, [])

    def test_a_name_the_invitation_dialog_does_not_state_refuses(self):
        """Rule 0.3's second naming, and it is a DIFFERENT surface from the
        first: the profile and the dialog must both name the same person."""
        page = StubPage(landing_text=LANDING.replace("A Person", "Someone Entirely Else"))
        code = self.run_connect(page, [profile(name="A Person")], [[]],
                                expect_name="A Person")
        self.assertEqual(code, 1)
        self.assertIn("does not name that person", self.said)

    def test_landing_somewhere_other_than_the_invitation_page_refuses(self):
        page = StubPage()
        br_lands = {INVITE_URL: "https://www.linkedin.com/feed/"}
        seq = [profile(), profile()]
        taken = {"p": 0}

        def fake_resolve(br, pace, url):
            i = min(taken["p"], len(seq) - 1)
            taken["p"] += 1
            pace.before_view("stub profile")
            pace.after_view()
            return seq[i]
        P.resolve_invite = fake_resolve
        N.Browser = StubBrowser(page, lands=br_lands)
        code = self.capture(N.connect, dict(url=PROFILE, note=None, note_file=None,
                                            expect_name=None, submit=False, dump=None,
                                            port=9224))
        self.assertEqual(code, 1)
        self.assertIn("landed on", self.said)

    def test_a_dialog_that_is_not_the_invitation_modal_refuses(self):
        """The modal is identified by what LABELS it, not by the word dialog:
        the withdraw confirmation on a neighbouring surface is a native <dialog>
        with an implicit role, and a probe for one is blind on the other."""
        page = StubPage(labelledby="something-else")
        code = self.run_connect(page, [profile()], [[]])
        self.assertEqual(code, 1)
        self.assertIn("dialog(s) labelled", self.said)


class TheNoteLimitIsReadOffThePage(ConnectCase):

    def test_the_limit_the_page_states_is_the_one_enforced(self):
        page = StubPage()
        code = self.run_connect(page, [profile(), profile()], [[]], note="hello there")
        self.assertIsNone(code, self.said)
        self.assertIn("note_limit_stated=300", self.said)

    def test_a_note_longer_than_the_stated_limit_refuses(self):
        page = StubPage()
        code = self.run_connect(page, [profile(), profile()], [[]], note="x" * 301)
        self.assertEqual(code, 1)
        self.assertIn("states a limit of 300", self.said)

    def test_a_note_of_250_would_have_been_refused_by_the_remembered_number(self):
        """The design remembered 200 and the page says 300. A verb carrying the
        remembered number would refuse a note LinkedIn accepts - which is the
        cheap direction of being wrong, and still wrong."""
        page = StubPage()
        self.assertIsNone(self.run_connect(page, [profile(), profile()], [[]],
                                           note="x" * 250), self.said)

    def test_a_page_that_states_no_limit_refuses_rather_than_defaulting(self):
        page = StubPage(note_text="Add a note to your invitation Cancel Send")
        code = self.run_connect(page, [profile(), profile()], [[]], note="hi")
        self.assertEqual(code, 1)
        self.assertIn("will not fall back on a remembered one", self.said)

    def test_a_note_that_does_not_arrive_in_the_box_refuses(self):
        page = StubPage(note_lost=3)
        code = self.run_connect(page, [profile(), profile()], [[]], note="hello there")
        self.assertEqual(code, 1)
        self.assertIn("did not arrive in the box", self.said)

    def test_the_pages_own_counter_disagreeing_refuses(self):
        """Two readings of the same thing: the textarea's value and the counter
        LinkedIn publishes beside it."""
        page = StubPage(counter_says=99)
        code = self.run_connect(page, [profile(), profile()], [[]], note="hello")
        self.assertEqual(code, 1)
        self.assertIn("counter says 99", self.said)

    def test_the_limit_is_taken_from_the_counter_when_the_sentence_is_gone(self):
        page = StubPage(note_text="Add a note to your invitation 0/280 Cancel Send")
        self.assertIsNone(self.run_connect(page, [profile(), profile()], [[]],
                                           note="hi"), self.said)
        self.assertIn("note_limit_stated=280", self.said)


# --------------------------------------------------------------- invitations

def received(name="A Person", slug="aperson", text=None, times=None):
    return {"label": "Accept %s’s invitation" % name,
            "profile": "https://www.linkedin.com/in/%s/" % slug,
            "name_on_link": name,
            "row_text": text if text is not None else "%s Some headline Ignore Accept" % name,
            "times": times or []}


class InvitationsCase(Phase3Case):

    def run_invitations(self, page, **kw):
        N.Browser = StubBrowser(page)
        self.page = page
        args = dict(limit=25, port=9224)
        args.update(kw)
        return self.capture(N.invitations, args)


class TheOneExceptionToTheZeroRowsRule(InvitationsCase):

    def test_a_parse_that_matches_the_pill_is_reported(self):
        page = StubPage(received=[received()], body="Manage invitations Focused (1) Verified (1)")
        self.assertIsNone(self.run_invitations(page), self.said)
        self.assertIn("RESULT invitations rows=1", self.said)
        self.assertIn("page_says=1", self.said)
        self.assertIn("pressed=nothing", self.said)

    def test_zero_rows_with_a_zero_pill_is_allowed(self):
        """This is the exception, and it is earned by the page publishing a
        number - not by an empty inbox being plausible."""
        page = StubPage(received=[], body="Manage invitations Focused (0) Verified (0)")
        self.assertIsNone(self.run_invitations(page), self.said)
        self.assertIn("rows=0", self.said)

    def test_zero_rows_with_no_pill_at_all_is_a_failure(self):
        """A4: where the page publishes no count, the general rule returns."""
        page = StubPage(received=[], body="Manage invitations Received Sent")
        code = self.run_invitations(page)
        self.assertEqual(code, 1)
        self.assertIn("Without a number to check against", self.said)

    def test_a_parse_that_disagrees_with_the_pill_is_a_failure(self):
        page = StubPage(received=[received()], body="Focused (7) Verified (7)")
        code = self.run_invitations(page)
        self.assertEqual(code, 1)
        self.assertIn("says Focused (7) and 1 row(s) were parsed", self.said)

    def test_the_pill_compared_against_is_the_one_whose_filter_is_on(self):
        """A4 again: the count is per filter. Comparing a Verified list against
        the Focused pill is how a half-read list passes."""
        page = StubPage(received=[received(), received("Another", "another")],
                        body="Focused (5) Verified (2)",
                        radios=[{"text": "Verified (2)", "checked": "true"}])
        self.assertIsNone(self.run_invitations(page), self.said)
        self.assertIn("filter=Verified", self.said)

    def test_two_filters_on_at_once_is_a_page_state_this_refuses(self):
        page = StubPage(received=[received()], body="Focused (1) Verified (1)",
                        radios=[{"text": "Verified (1)", "checked": "true"},
                                {"text": "Other (1)", "checked": "true"}])
        code = self.run_invitations(page)
        self.assertEqual(code, 1)
        self.assertIn("switched on at once", self.said)


class WhatAReceivedRowActuallyStates(InvitationsCase):

    def test_a_row_with_no_note_and_no_time_reports_null_for_both(self):
        """Design 4.6 asks for both and the measured rows state neither. The
        fields are reported as null - and the RESULT line publishes how many
        rows carried each, so a reader can see that the answer is 'the page did
        not say' rather than 'nobody wrote a note'."""
        page = StubPage(received=[received()], body="Focused (1)")
        self.assertIsNone(self.run_invitations(page), self.said)
        self.assertIn('"note": null', self.said)
        self.assertIn('"when": null', self.said)
        self.assertIn("with_note=0", self.said)
        self.assertIn("with_when=0", self.said)

    def test_a_row_that_does_state_them_reports_them(self):
        """The parser looks for both, so the day a row carries either it is
        reported without a change here."""
        page = StubPage(received=[received(text='A Person “We met at the conference” '
                                                'Ignore Accept',
                                           times=[{"datetime": "2026-09-01", "text": "1w"}])],
                        body="Focused (1)")
        self.assertIsNone(self.run_invitations(page), self.said)
        self.assertIn("We met at the conference", self.said)
        self.assertIn("with_when=1", self.said)

    def test_the_name_comes_off_the_accept_control_that_states_it(self):
        page = StubPage(received=[received("Jo Bloggs", "jobloggs")], body="Focused (1)")
        self.run_invitations(page)
        self.assertIn('"name": "Jo Bloggs"', self.said)

    def test_reading_our_own_invitations_is_uncapped(self):
        page = StubPage(received=[received()], body="Focused (1)")
        self.run_invitations(page)
        self.assertEqual(len(B.views_taken("view")), 0)
        self.assertEqual(len(B.views_taken("view_self")), 1)


# ------------------------------------------------------------ follow/unfollow

def follow_state(following, pressed=None, cls=None, label=None, n=1, total=1, card=True):
    """A control whose three signals can be made to disagree on purpose."""
    return {"total_on_page": total, "in_top_card": n, "top_card_present": card,
            "controls": [{"pressed": ("true" if following else "false")
                          if pressed is None else pressed,
                          "label": ("Following" if following else "Follow")
                          if label is None else label,
                          "text": "Following" if following else "Follow",
                          "following_class": following if cls is None else cls,
                          "disabled": False}] * n}


class FollowCase(Phase3Case):

    def run_follow(self, fn, states, **kw):
        seq = list(states)
        taken = {"i": 0}
        page = StubPage(follow=seq[0])

        def read(url, where, settle=6):
            i = min(taken["i"], len(seq) - 1)
            page.follow = seq[i]
            taken["i"] += 1
            page.url = "https://www.linkedin.com/company/acme/about/?viewAsMember=true"
            return page.url
        br = StubBrowser(page)
        br.read = read
        N.Browser = br
        self.page, self.browser = page, br
        args = dict(url="acme", dump=None, port=9224)
        args.update(kw)
        return self.capture(fn, args)


class TheFollowStateIsReadFromThreeSignals(FollowCase):

    def test_following_a_page_we_do_not_follow_flips_and_asserts(self):
        code = self.run_follow(N.follow, [follow_state(False), follow_state(True)])
        self.assertIsNone(code, self.said)
        self.assertIn("RESULT follow", self.said)
        self.assertIn("changed=true", self.said)
        self.assertEqual(self.browser.presses and 1 or 0, 1)

    def test_a_page_already_followed_presses_nothing(self):
        code = self.run_follow(N.follow, [follow_state(True)])
        self.assertIsNone(code, self.said)
        self.assertIn("pressed=nothing", self.said)
        self.assertEqual(self.browser.presses, [])

    def test_unfollow_is_the_same_verb_the_other_way(self):
        code = self.run_follow(N.unfollow, [follow_state(True), follow_state(False)])
        self.assertIsNone(code, self.said)
        self.assertIn("RESULT unfollow", self.said)

    def test_a_control_that_did_not_flip_is_a_failure(self):
        code = self.run_follow(N.follow, [follow_state(False), follow_state(False)])
        self.assertEqual(code, 1)
        self.assertIn("still reads", self.said)

    def test_aria_pressed_disagreeing_with_the_class_token_refuses(self):
        code = self.run_follow(N.follow, [follow_state(False, pressed="true")])
        self.assertEqual(code, 1)
        self.assertIn("disagrees with itself", self.said)

    def test_the_name_disagreeing_with_the_rest_refuses(self):
        code = self.run_follow(N.follow, [follow_state(True, label="Follow")])
        self.assertEqual(code, 1)
        self.assertIn("disagrees with itself", self.said)

    def test_more_than_one_control_on_the_top_card_refuses(self):
        """Recommendation cards further down the page carry the same control
        minus the org-top-card- part, so an unscoped search flips a Page nobody
        asked about."""
        code = self.run_follow(N.follow, [follow_state(False, n=2, total=9)])
        self.assertEqual(code, 1)
        self.assertIn("found 2", self.said)

    def test_no_top_card_refuses(self):
        code = self.run_follow(N.follow, [follow_state(False, card=False)])
        self.assertEqual(code, 1)
        self.assertIn("no top card", self.said)

    def test_following_takes_an_outbound_slot(self):
        """It reaches somebody: a Page admin sees the follower count move."""
        self.run_follow(N.follow, [follow_state(False), follow_state(True)])
        self.assertEqual(B.Pace().count("follow"), 1)


# ------------------------------------------------------------ invite-to-follow

def invite_dialog(credits=50, total=50, checked=0, options=20):
    return {"found": True, "text": "Invite to follow Expand your reach by inviting others to "
                                   "follow your page. %d/%d credits available - Credit "
                                   "refill: October 1, 2026" % (credits, total),
            "options": options, "selects": ["Select A Person"], "checked": checked,
            "buttons": []}


class InviteToFollowCase(Phase3Case):

    def run_invite(self, dialogs, **kw):
        seq = list(dialogs)
        taken = {"i": 0}
        page = StubPage(invite=seq[0])

        def read(url, where, settle=6):
            i = min(taken["i"], len(seq) - 1)
            page.invite = seq[i]
            # A RELOAD CLEARS THE SELECTION, which is what the live dialog does
            # and what makes "the reloaded dialog still has rows ticked" a real
            # failure rather than an artefact of the stub remembering.
            page.checked = seq[i].get("checked", 0)
            taken["i"] += 1
            page.url = "https://www.linkedin.com/company/107519091/admin/dashboard/?invite=true"
            return page.url
        br = StubBrowser(page)
        br.read = read
        N.Browser = br
        self.page, self.browser = page, br
        args = dict(page="107519091", name=["A Person"], submit=False, dump=None, port=9224)
        args.update(kw)
        return self.capture(N.invite_to_follow, args)


class TheCreditIsTheProof(InviteToFollowCase):

    def test_a_staged_run_reads_the_credits_and_proves_they_did_not_move(self):
        page_seq = [invite_dialog(50), invite_dialog(50)]
        code = self.run_invite(page_seq)
        self.assertIsNone(code, self.said)
        self.assertIn("RESULT invite-to-follow-staged", self.said)
        self.assertIn("credits=50 unchanged=true", self.said)
        self.assertFalse(self.page.invited)

    def test_a_staged_run_that_spent_a_credit_is_a_failure(self):
        code = self.run_invite([invite_dialog(50), invite_dialog(49)])
        self.assertEqual(code, 1)
        self.assertIn("A staged run must spend nothing", self.said)

    def test_a_staged_run_that_left_a_selection_behind_is_a_failure(self):
        code = self.run_invite([invite_dialog(50), invite_dialog(50, checked=1)])
        self.assertEqual(code, 1)
        self.assertIn("left a selection behind", self.said)

    def test_fewer_credits_than_people_refuses_before_selecting(self):
        code = self.run_invite([invite_dialog(1)], name=["A", "B", "C"])
        self.assertEqual(code, 1)
        self.assertIn("credit(s) left", self.said)
        self.assertEqual(self.page.checked, 0)

    def test_a_dialog_with_no_credit_line_refuses(self):
        d = invite_dialog()
        d["text"] = "Invite to follow Expand your reach by inviting others to follow your page."
        code = self.run_invite([d])
        self.assertEqual(code, 1)
        self.assertIn("states no credit count", self.said)

    def test_no_dialog_at_all_refuses(self):
        code = self.run_invite([{"found": False, "dialogs": 0, "texts": []}])
        self.assertEqual(code, 1)
        self.assertIn("states", self.said)

    def test_more_than_five_people_refuses(self):
        code = self.run_invite([invite_dialog()], name=["a", "b", "c", "d", "e", "f"])
        self.assertEqual(code, 1)
        self.assertIn("at most", self.said)

    def test_no_name_at_all_refuses(self):
        code = self.run_invite([invite_dialog()], name=[])
        self.assertEqual(code, 1)
        self.assertIn("--name is required", self.said)

    def test_a_name_matching_two_rows_refuses(self):
        page_seq = [invite_dialog(50), invite_dialog(50)]
        seq = list(page_seq)
        taken = {"i": 0}
        page = StubPage(invite=seq[0], select_count=2)

        def read(url, where, settle=6):
            i = min(taken["i"], len(seq) - 1)
            page.invite = seq[i]
            page.checked = seq[i].get("checked", 0)
            taken["i"] += 1
            page.url = "https://www.linkedin.com/company/107519091/admin/dashboard/?invite=true"
            return page.url
        br = StubBrowser(page)
        br.read = read
        N.Browser = br
        self.page = page
        code = self.capture(N.invite_to_follow,
                            dict(page="107519091", name=["A Person"], submit=False,
                                 dump=None, port=9224))
        self.assertEqual(code, 1)
        self.assertIn("has no outcome here", self.said)

    def test_a_real_run_proves_itself_on_the_credit_falling_by_exactly_one(self):
        """THE SUBMIT PATH, AND IT WAS UNCOVERED UNTIL A REVERT SAID SO.

        Every guard in this file was watched failing by taking it out and
        re-running - and taking out the credit-drop assertion left the suite
        GREEN, because nothing here had ever driven `--submit`. The docstring at
        the top of this file said the credit is the proof; no test made that
        true. That is proof covering the wrong thing, and the only reason it was
        found is that the revert was actually performed rather than reasoned
        about.
        """
        code = self.run_invite([invite_dialog(50), invite_dialog(49)], submit=True)
        self.assertIsNone(code, self.said)
        self.assertIn("RESULT invited-to-follow", self.said)
        self.assertIn("credits=50->49", self.said)
        self.assertTrue(self.page.invited)

    def test_a_credit_that_did_not_move_is_a_failure_however_the_page_looks(self):
        """A row that says "Invited" costs nothing and proves nothing. This is
        the case the revert exposed as untested."""
        code = self.run_invite([invite_dialog(50), invite_dialog(50)], submit=True)
        self.assertEqual(code, 1)
        self.assertIn("THE CREDIT IS THE THING THAT IS ACTUALLY SPENT", self.said)

    def test_two_credits_gone_for_one_invitation_is_also_a_failure(self):
        """The assertion is an EQUALITY and not "it went down". A page that
        spent two credits for one invitation is a thing to hear about."""
        code = self.run_invite([invite_dialog(50), invite_dialog(48)], submit=True)
        self.assertEqual(code, 1)
        self.assertIn("should have taken it to 49", self.said)

    def test_a_real_run_takes_one_outbound_slot_per_person(self):
        self.run_invite([invite_dialog(50), invite_dialog(48)], name=["A Person", "Another"],
                        submit=True)
        self.assertEqual(B.Pace().count("invite"), 2)

    def test_the_dialog_is_uncapped_because_the_page_is_ours(self):
        self.run_invite([invite_dialog(50), invite_dialog(50)])
        self.assertEqual(len(B.views_taken("view")), 0)
        self.assertEqual(len(B.views_taken("view_self")), 2)


if __name__ == "__main__":
    unittest.main()
