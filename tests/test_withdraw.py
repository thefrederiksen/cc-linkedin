# -*- coding: utf-8 -*-
"""The guards on `withdraw`, each driven with a stub browser so no page is
opened and nobody's invitation is touched.

WHAT IS BEING GUARDED, AND WHY EACH ONE IS HERE.

  * A5 - the withdraw control is an ANCHOR whose href is the feed. An activation
    the page does not swallow navigates away and withdraws NOTHING, silently.
    So landing anywhere but the invitation manager is a FAIL that names exactly
    that. Watched failing by pointing the stub at the feed.
  * "the row is gone" is an ABSENCE and an absence certifies itself. A broken
    selector, a half-loaded list and a page that failed to render all produce a
    missing row for free. So the assertion is a PRESENCE - the count fell by
    exactly one, the page's own pill agrees, and the rows that left are exactly
    the one row. Watched failing on each of the three separately.
  * Rule 0.3 - an irreversible act names its target twice. --expect-name is
    required with --submit, and it is compared against the name read off the
    control that is about to be pressed.
  * The age filter. LinkedIn displays a rounded-down relative age and never a
    date, so an age proves a MINIMUM. An age the parser cannot read must refuse,
    not default to zero and not default to old.

THE ONE THING THESE CANNOT PROVE, said plainly: they do not prove that pressing
the control withdraws anything. That is a live-page fact and it was proven once,
by hand, on 2026-09-10 - the run is in docs/phase-3-withdraw-report.md. What is
proven here is everything that happens either side of the press.
"""
import argparse
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import browser as B
from cc_linkedin_kit import connections as N


def row(slug, name, age="Sent 3 months ago"):
    return {"index": 0, "label": "Withdraw invitation sent to " + name,
            "href": "https://www.linkedin.com/", "profile": "/in/%s/" % slug, "age": age}


# What the live confirmation says, measured 2026-09-10. The wording matters:
# the page says "UP TO 3 weeks" and the design remembered "about three weeks".
CONFIRMATION_TEXT = ("Withdraw invitation\n\nIf you withdraw now, you won’t be able to "
                     "resend to this person for up to 3 weeks.\n\nCancel\nWithdraw")


class StubPage(object):
    """Just enough page for the verb: a URL, a locator, and a confirmation
    dialog that appears only once the withdraw control has been activated -
    which is what the live page does."""

    def __init__(self, url):
        self.url = url
        self.browser = None
        self.activated_once = False
        # The dialog the stub serves after activation. A test sets this to []
        # to model a page that stopped confirming, or edits the buttons to model
        # one this verb cannot identify.
        self.dialog = {"role": "dialog", "modal": None, "text": CONFIRMATION_TEXT,
                       "buttons": ["Dismiss", "Cancel", None]}
        self.confirm_buttons = 1
        self.marker = False

    def activated(self):
        """The page's own record that its withdraw control was activated - by a
        click now, not a keystroke. Measured 2026-09-10: focus + Enter on this
        anchor did nothing at all, three times."""
        self.activated_once = True
        if self.browser is not None:
            self.browser.press(None, "clicked")

    def dialogs(self):
        if not self.activated_once or self.dialog is None:
            return []
        d = dict(self.dialog)
        if self.browser is not None and self.browser.label:
            d["buttons"] = [b if b is not None else self.browser.label for b in d["buttons"]]
        return [d]

    def locator(self, sel):
        if "dialog" in sel:
            return StubLocator(self, self.confirm_buttons, dialog=True)
        return StubLocator(self, 1)

    def get_by_role(self, role, name=None):
        return StubLocator(self, 1)

    def evaluate(self, js, *a):
        if "__ccWithdrawMarker = 1" in js:
            self.marker = True
            return None
        if "__ccWithdrawMarker === 1" in js:
            return self.marker
        if js in (N.DIALOG_JS, N.APPEARED_JS):
            return self.dialogs()
        return []


class StubLocator(object):

    def __init__(self, page, n, dialog=False):
        self.page, self.n, self.dialog = page, n, dialog
        self.first = self

    def locator(self, sel):
        """The confirm button, looked for INSIDE the open dialog."""
        return StubLocator(self.page, self.page.confirm_buttons if self.page.dialogs() else 0)

    def count(self):
        return self.n

    def bounding_box(self):
        return {"x": 10, "y": 20, "width": 80, "height": 24}

    def click(self, timeout=None):
        self.page.activated()


class StubBrowser(object):
    """Serves a scripted sequence of Sent lists. Each `load` takes the next."""

    def __init__(self, lists, url_after_press=None, pill=None, label=None):
        self.lists = list(lists)
        self.url_after_press = url_after_press
        self.pill = pill
        self.label = label
        self.page = StubPage("https://www.linkedin.com/mynetwork/invitation-manager/sent/")
        self.page.browser = self
        self.presses = []

    def __call__(self, port):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, url, where, settle=6):
        return "https://www.linkedin.com/mynetwork/invitation-manager/sent/"

    def press(self, locator, what):
        self.presses.append(what)
        if self.url_after_press:
            self.page.url = self.url_after_press


class WithdrawCase(unittest.TestCase):
    """Every case shares the same rig: a temporary pacing directory, no gaps,
    and a SentList whose loading is replaced by the scripted lists."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cc-linkedin-withdraw-")
        self._state, B.STATE_DIR = B.STATE_DIR, self.dir
        self._vgap, B.Pace.VIEW_GAP = B.Pace.VIEW_GAP, (0, 0)
        self._ogap, B.Pace.GAP = B.Pace.GAP, (0, 0)
        self._browser, N.Browser = N.Browser, None
        self._load = N.SentList.load
        self._settle, N.SCROLL_SETTLE = N.SCROLL_SETTLE, 0
        self._act, N.ACTIVATE_SETTLE = N.ACTIVATE_SETTLE, 0
        del B._VIEWS[:]

    def tearDown(self):
        B.STATE_DIR = self._state
        B.Pace.VIEW_GAP = self._vgap
        B.Pace.GAP = self._ogap
        N.Browser = self._browser
        N.SentList.load = self._load
        N.SCROLL_SETTLE = self._settle
        N.ACTIVATE_SETTLE = self._act
        del B._VIEWS[:]
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_withdraw(self, lists, pills=None, url_after_press=None,
                     no_dialog=False, confirm_buttons=None, **kw):
        """Drive the verb over a scripted sequence of Sent lists. Returns the
        SystemExit code, or None when it completed."""
        seq = list(lists)
        pills = list(pills) if pills is not None else [len(x) for x in seq]
        taken = {"i": 0}

        def fake_load(self):
            i = taken["i"]
            taken["i"] += 1
            if i >= len(seq):
                raise AssertionError("the verb loaded the list more times than scripted")
            self.rows = list(seq[i])
            self.pill = pills[i]
            self.pace.before_self_view("stub Sent tab")
            self.pace.after_view()
            return self

        N.SentList.load = fake_load
        target = None
        for r in (seq[0] if seq else []):
            if isinstance(r, dict) and r.get("profile", "").strip("/").endswith("target"):
                target = r["label"]
        br = StubBrowser(seq, url_after_press=url_after_press, label=target)
        if no_dialog:
            br.page.dialog = None
        if confirm_buttons is not None:
            br.page.confirm_buttons = confirm_buttons
        N.Browser = br
        self.browser = br
        args = dict(url="https://www.linkedin.com/in/target/", expect_name=None,
                    older_than_months=None, submit=False, dump=None, port=9224)
        args.update(kw)
        # WHAT THE REFUSAL SAID, not merely that it refused. Two different
        # refusals both exit 1, and a test that checks only the code passes for
        # the wrong reason: an age parser that returned 0 for an unreadable age
        # would still be refused by a two-month filter, and the test would stay
        # green while the parser had started guessing.
        out = io.StringIO()
        stdout, sys.stdout = sys.stdout, out
        try:
            N.withdraw(argparse.Namespace(**args))
        except SystemExit as exc:
            return exc.code
        finally:
            sys.stdout = stdout
            self.said = out.getvalue()
            stdout.write(self.said)
        return None


# ---------------------------------------------------------------- A5

class TheAnchorTrap(WithdrawCase):
    """A5. The control is an <a href="https://www.linkedin.com/">. If the page's
    handler does not swallow the activation the browser goes to the FEED and the
    invitation is untouched - and nothing says so."""

    def test_landing_on_the_feed_is_a_failure(self):
        code = self.run_withdraw(
            [[row("target", "A Person")], [[]]],
            url_after_press="https://www.linkedin.com/feed/",
            submit=True, expect_name="A Person")
        self.assertEqual(code, 1)

    def test_staying_on_the_invitation_manager_is_not(self):
        code = self.run_withdraw(
            [[row("target", "A Person"), row("other", "Someone Else")],
             [row("other", "Someone Else")]],
            submit=True, expect_name="A Person")
        self.assertIsNone(code)
        # TWO activations, and both are the same single withdrawal: the row's
        # control, then the confirmation's. Before the confirmation was measured
        # this verb pressed once and believed it was finished.
        self.assertEqual(len(self.browser.presses), 2)


# ------------------------------------------------- the confirmation

class TheConfirmation(WithdrawCase):
    """MEASURED 2026-09-10, and the reason it took four attempts to withdraw one
    invitation. It is a NATIVE <dialog>, which carries an IMPLICIT role and so
    has no role attribute: '[role="dialog"]' does not match it. The probe was
    blind, and because its pass condition was an ABSENCE it reported "no
    confirmation appeared" three times while the confirmation was open on screen
    intercepting every pointer event.

    So a missing confirmation is now a FAILURE, not a shortcut. An absence that
    used to be a presence is a broken instrument until something proves
    otherwise."""

    def test_no_confirmation_is_a_failure_and_not_a_shortcut(self):
        code = self.run_withdraw(
            [[row("target", "A Person"), row("other", "Someone Else")],
             [row("other", "Someone Else")]],
            no_dialog=True, submit=True, expect_name="A Person")
        self.assertEqual(code, 1)
        self.assertIn("no confirmation dialog appeared", self.said)

    def test_a_confirm_control_it_cannot_identify_is_never_pressed(self):
        """The confirm button's visible text is "Withdraw", and so is the
        dialog's heading. It is identified by the SENTENCE naming this person,
        and when that is not there the verb stops rather than press one of the
        three things on screen that say the word."""
        code = self.run_withdraw(
            [[row("target", "A Person")]],
            confirm_buttons=0, submit=True, expect_name="A Person")
        self.assertEqual(code, 1)
        self.assertIn("cannot identify which control confirms it", self.said)
        self.assertEqual(len(self.browser.presses), 1,
                         "the row was activated; the confirmation must not have been")

    def test_two_matching_confirm_controls_is_ambiguity(self):
        code = self.run_withdraw(
            [[row("target", "A Person")]],
            confirm_buttons=2, submit=True, expect_name="A Person")
        self.assertEqual(code, 1)

    def test_what_the_dialog_said_reaches_the_result_line(self):
        code = self.run_withdraw(
            [[row("target", "A Person"), row("other", "Someone Else")],
             [row("other", "Someone Else")]],
            submit=True, expect_name="A Person")
        self.assertIsNone(code)
        self.assertIn("RESULT withdrawn", self.said)
        self.assertIn("up to 3 weeks", self.said,
                      "a caller who withdraws without knowing the restriction has spent "
                      "something they cannot get back")


# ------------------------------------------------- the proof is a number

class TheRowIsGoneIsNotEnough(WithdrawCase):
    """Each of these is a way for the row to be missing without the withdrawal
    having happened. Every one must FAIL."""

    def test_the_row_is_still_there(self):
        code = self.run_withdraw(
            [[row("target", "A Person"), row("other", "Someone Else")],
             [row("target", "A Person"), row("other", "Someone Else")]],
            submit=True, expect_name="A Person")
        self.assertEqual(code, 1)

    def test_the_whole_list_collapsed(self):
        """A page that failed to render loses every row at once, which satisfies
        'the row is gone' perfectly."""
        code = self.run_withdraw(
            [[row("target", "A Person"), row("other", "Someone Else"), row("third", "A Third")],
             [row("other", "Someone Else")]],
            submit=True, expect_name="A Person")
        self.assertEqual(code, 1)

    def test_the_pages_own_count_disagrees(self):
        """The list is one shorter and the pill did not move - so the list was
        read half-loaded, not shortened."""
        code = self.run_withdraw(
            [[row("target", "A Person"), row("other", "Someone Else")],
             [row("other", "Someone Else")]],
            pills=[2, 2], submit=True, expect_name="A Person")
        self.assertEqual(code, 1)

    def test_a_different_row_left_as_well(self):
        code = self.run_withdraw(
            [[row("target", "A Person"), row("other", "Someone Else"), row("third", "A Third")],
             [row("other", "Someone Else"), row("fourth", "A Fourth")]],
            submit=True, expect_name="A Person")
        self.assertEqual(code, 1)


# ---------------------------------------------------------------- rule 0.3

class NamedTwice(WithdrawCase):

    def test_submit_without_expect_name_refuses(self):
        code = self.run_withdraw([[row("target", "A Person")]], submit=True)
        self.assertEqual(code, 1)

    def test_a_mismatched_name_refuses_before_pressing(self):
        code = self.run_withdraw(
            [[row("target", "A Person")]], submit=True, expect_name="Somebody Different")
        self.assertEqual(code, 1)
        self.assertEqual(self.browser.presses, [],
                         "the refusal must come BEFORE the control is touched")

    def test_the_name_is_read_off_the_control_not_the_url(self):
        code = self.run_withdraw(
            [[row("target", "A Person"), row("other", "Someone Else")],
             [row("other", "Someone Else")]],
            submit=True, expect_name="a person")
        self.assertIsNone(code, "the comparison is case-folded, not case-sensitive")

    def test_a_control_whose_label_is_not_the_sentence_refuses(self):
        bad = row("target", "A Person")
        bad["label"] = "Withdraw"
        code = self.run_withdraw([[bad]], submit=True, expect_name="A Person")
        self.assertEqual(code, 1)


# ---------------------------------------------------------------- the age

class AgeProvesAMinimum(unittest.TestCase):
    """LinkedIn displays a rounded-down relative age and never a date, so an age
    proves a LOWER BOUND. Nothing here may round up."""

    def test_months(self):
        self.assertEqual(N.age_at_least_months("Sent 3 months ago"), 3)
        self.assertEqual(N.age_at_least_months("Sent 1 month ago"), 1)
        self.assertEqual(N.age_at_least_months("6 months ago"), 6)

    def test_years(self):
        self.assertEqual(N.age_at_least_months("Sent 1 year ago"), 12)
        self.assertEqual(N.age_at_least_months("Sent 2 years ago"), 24)

    def test_everything_shorter_than_a_month_proves_nothing(self):
        for line in ("Sent 11 hours ago", "Sent yesterday", "Sent 1 week ago",
                     "Sent 3 weeks ago", "Sent 29 days ago", "Sent 2 minutes ago"):
            self.assertEqual(N.age_at_least_months(line), 0, line)

    def test_three_weeks_is_not_a_month(self):
        """The row that would make a two-month filter act on a three-week-old
        invitation if weeks were divided into months."""
        self.assertEqual(N.age_at_least_months("Sent 3 weeks ago"), 0)

    def test_an_unreadable_age_is_none_and_not_zero(self):
        for line in ("", None, "Sent a while back", "Sent on Tuesday", "Sent"):
            self.assertIsNone(N.age_at_least_months(line), repr(line))


class TheAgeFilterRefusesRatherThanGuesses(WithdrawCase):

    def test_a_row_newer_than_asked_for_is_refused(self):
        code = self.run_withdraw(
            [[row("target", "A Person", "Sent 1 month ago")]],
            older_than_months=2, submit=True, expect_name="A Person")
        self.assertEqual(code, 1)
        self.assertEqual(self.browser.presses, [])

    def test_an_unreadable_age_is_refused_when_a_filter_was_asked_for(self):
        code = self.run_withdraw(
            [[row("target", "A Person", "Sent a while back")]],
            older_than_months=2, submit=True, expect_name="A Person")
        self.assertEqual(code, 1)
        self.assertEqual(self.browser.presses, [])
        # WHICH refusal, not just that one fired. A parser that returned 0 for an
        # age it could not read would also be refused here - by the wrong test,
        # for the wrong reason - and would then act on that same row the moment
        # the filter was --older-than-months 0.
        self.assertIn("cannot turn that into a number of months", self.said)

    def test_an_unreadable_age_is_refused_even_by_a_zero_filter(self):
        """The row the previous test cannot tell apart on its own. Asking for
        "at least 0 months" is satisfied by everything - except an age nobody
        could read, which is not a small number, it is not a number."""
        code = self.run_withdraw(
            [[row("target", "A Person", "Sent a while back")]],
            older_than_months=0, submit=True, expect_name="A Person")
        self.assertEqual(code, 1)
        self.assertEqual(self.browser.presses, [])
        self.assertIn("cannot turn that into a number of months", self.said)

    def test_a_qualifying_row_passes_the_filter(self):
        code = self.run_withdraw(
            [[row("target", "A Person", "Sent 3 months ago"), row("other", "Someone Else")],
             [row("other", "Someone Else")]],
            older_than_months=2, submit=True, expect_name="A Person")
        self.assertIsNone(code)


# ---------------------------------------------------------------- staging

class StagedPressesNothing(WithdrawCase):

    def test_a_staged_run_touches_no_control(self):
        code = self.run_withdraw(
            [[row("target", "A Person")], [row("target", "A Person")]])
        self.assertIsNone(code)
        self.assertEqual(self.browser.presses, [],
                         "a staged withdraw must not activate the control at all - there "
                         "may be no confirmation step to escape from")

    def test_a_staged_run_proves_the_row_survived(self):
        """Rule 0.1: a staged run asserts the PRE-ACTION state is still there."""
        code = self.run_withdraw(
            [[row("target", "A Person")], []])
        self.assertEqual(code, 1)


# ---------------------------------------------------------------- targeting

class Targeting(WithdrawCase):

    def test_no_such_invitation_fails(self):
        code = self.run_withdraw([[row("other", "Someone Else")]])
        self.assertEqual(code, 1)

    def test_two_rows_for_one_person_is_ambiguity_and_ambiguity_has_no_outcome(self):
        code = self.run_withdraw(
            [[row("target", "A Person"), row("target", "A Person Again")]],
            submit=True, expect_name="A Person")
        self.assertEqual(code, 1)

    def test_a_slug_is_read_out_of_a_full_url(self):
        self.assertEqual(N._slug("https://www.linkedin.com/in/somebody/"), "somebody")
        self.assertEqual(N._slug("/in/somebody"), "somebody")
        self.assertEqual(N._slug("somebody"), "somebody")


# ---------------------------------------------------------------- pacing

class WithdrawIsOutbound(WithdrawCase):
    """A withdrawal changes something on another person's side and twenty in a
    burst is what an automated account looks like. It takes the outbound gap and
    an outbound cap, not a view's."""

    def test_it_has_a_daily_cap(self):
        self.assertEqual(B.Pace.CAPS["withdraw"], 20)

    def test_a_real_withdraw_reserves_an_outbound_slot(self):
        self.run_withdraw(
            [[row("target", "A Person"), row("other", "Someone Else")],
             [row("other", "Someone Else")]],
            submit=True, expect_name="A Person")
        self.assertEqual(B.Pace().count("withdraw"), 1)

    def test_a_staged_run_spends_nothing_outbound(self):
        self.run_withdraw([[row("target", "A Person")], [row("target", "A Person")]])
        self.assertEqual(B.Pace().count("withdraw"), 0)

    def test_the_cap_refuses_the_twenty_first(self):
        p = B.Pace()
        for _ in range(B.Pace.CAPS["withdraw"]):
            p.before("withdraw")
        with self.assertRaises(SystemExit):
            p.before("withdraw")


# ------------------------------------------------- what the caller is told

class TheResultLineCarriesTheConsequence(unittest.TestCase):
    """Design 4.2: a caller who withdraws without knowing about the re-invite
    restriction has spent something they cannot get back."""

    def test_what_the_page_said_is_quoted(self):
        got = N._restriction({"consequence_text_on_screen": [
            "You won't be able to resend an invitation to this person for 3 weeks."]})
        self.assertTrue(got.startswith("stated-on-screen: "), got)
        self.assertIn("3 weeks", got)

    def test_a_silent_page_is_reported_as_silent_and_no_number_is_invented(self):
        got = N._restriction({"consequence_text_on_screen": [], "confirmation": []})
        self.assertTrue(got.startswith("not-stated-on-screen: "), got)
        self.assertNotIn("three weeks", got.lower())
        self.assertNotIn("21 days", got)


if __name__ == "__main__":
    unittest.main()
