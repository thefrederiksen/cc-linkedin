# -*- coding: utf-8 -*-
"""The guards on `message`, against plain values. No browser.

WHAT IS BEING GUARDED, AND WHY.

  * THE WRONG-NAME DM (2026-07-21). A text that opens "Hi X" must greet the
    participant the page names, by first name. Pinned both ways: the mismatch
    refuses, and the ordinary match - including accents and case - passes,
    because a guard that refuses everything gets switched off.
  * ENTER SENDS. The module must contain no path that presses Enter alone and
    must never call Browser.type_text, which presses Enter per newline. That is
    a property of the SOURCE, so it is checked against the source.
  * PROOF OF SEND is a NEW message from us with this text - a urn that was not
    on the page before we typed. An old message that happens to match must not
    pass, and nor must a matching message from the other person.
  * A staged run's "the composer is empty" must be positive: the text is blank
    AND Send is disabled. A blank text with Send enabled is not empty.

What these cannot prove: that the selectors still match the live page, and that
Shift+Enter is still a line break there. Those are proven by the live staged
run, whose read-back compares every line.
"""
import contextlib
import io
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import messaging as M

ME = "Owner Person"


def msg(sender, text, urn):
    return {"sender": sender, "text": text, "urn": urn}


class Greeting(unittest.TestCase):

    def test_the_wrong_first_name_refuses(self):
        self.assertIsNotNone(M.greeting_problem("Hi Robert, quick one.", "Jane Example"))

    def test_hey_and_hello_are_checked_too(self):
        self.assertIsNotNone(M.greeting_problem("Hey Robert", "Jane Example"))
        self.assertIsNotNone(M.greeting_problem("hello robert!", "Jane Example"))

    def test_the_right_first_name_passes(self):
        self.assertIsNone(M.greeting_problem("Hi Jane, great to meet you.", "Jane Example"))

    def test_case_and_accents_are_folded(self):
        self.assertIsNone(M.greeting_problem("hi renee,", "Renée Exämple"))

    def test_the_surname_is_not_the_first_name(self):
        self.assertIsNotNone(M.greeting_problem("Hi Example,", "Jane Example"))

    def test_no_greeting_is_not_checked(self):
        self.assertIsNone(M.greeting_problem("Thanks for yesterday.", "Jane Example"))
        self.assertIsNone(M.greeting_problem("Hiring news: ...", "Jane Example"))

    def test_a_greeting_alone_on_its_line_names_nobody(self):
        self.assertIsNone(M.greeting_problem("Hi\n\nThanks for yesterday.", "Jane Example"))

    def test_there_is_not_a_name(self):
        self.assertIsNone(M.greeting_problem("Hi there, quick one.", "Jane Example"))

    def test_a_greeting_with_no_participant_refuses(self):
        self.assertIsNotNone(M.greeting_problem("Hi Jane", ""))

    # Review defect 4, 2026-10-04: each of these slipped past the first guard.
    def test_a_no_break_space_does_not_hide_the_name(self):
        self.assertIsNotNone(M.greeting_problem("Hi Robert, quick one.", "Jane Example"))

    def test_punctuation_before_the_name_does_not_hide_it(self):
        self.assertIsNotNone(M.greeting_problem("Hi, Robert", "Jane Example"))
        self.assertIsNone(M.greeting_problem("Hi, Jane", "Jane Example"))

    def test_a_greeting_then_other_words_on_its_line_refuses(self):
        self.assertIsNotNone(M.greeting_problem("Hello! Quick question for you.", "Jane Example"))

    def test_a_bare_greeting_line_passes(self):
        self.assertIsNone(M.greeting_problem("Hi,\nquick question.", "Jane Example"))


class InvisibleCharacters(unittest.TestCase):

    def write(self, data):
        fd, p = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        with open(p, "wb") as f:
            f.write(data)
        self.addCleanup(os.remove, p)
        return p

    def test_a_bom_is_not_typed_and_the_greeting_is_still_checked(self):
        p = self.write("﻿Hi Robert, quick one.".encode("utf-8"))
        text = M.load_text(None, p)
        self.assertEqual(text, "Hi Robert, quick one.")
        self.assertIsNotNone(M.greeting_problem(text, "Jane Example"))

    def test_a_zero_width_space_refuses(self):
        with self.assertRaises(SystemExit):
            M.load_text("​Hi Robert", None)

    def test_a_direction_mark_refuses(self):
        with self.assertRaises(SystemExit):
            M.load_text("Hi Jane ‏", None)

    def test_an_emoji_with_a_joiner_is_allowed(self):
        self.assertTrue(M.load_text("Thanks \U0001f468‍\U0001f4bb", None))


class NeverEnter(unittest.TestCase):
    """Read the module's own source. Enter sends on this surface."""

    def setUp(self):
        with io.open(M.__file__, encoding="utf-8") as f:
            self.src = f.read()
        # Code only: drop the docstrings and comments, which talk ABOUT Enter.
        code = re.sub(r'"""[\s\S]*?"""', "", self.src)
        self.code = "\n".join(l.split("#")[0] for l in code.splitlines())

    def test_no_bare_enter_is_pressed(self):
        presses = re.findall(r"press\(\s*['\"]([^'\"]+)['\"]", self.code)
        self.assertTrue(presses, "the scan found no key presses at all - a broken instrument")
        self.assertIn("Shift+Enter", presses)
        self.assertNotIn("Enter", presses)
        self.assertFalse([p for p in presses if p.lower() in ("enter", "return", "numpadenter")])

    def test_type_text_is_never_used(self):
        self.assertNotIn("type_text", self.code)

    def test_browser_press_is_never_used(self):
        """Browser.press is focus + Enter: on a composer, that is a send."""
        self.assertNotIn("br.press(", self.code)
        self.assertNotIn(".press(self", self.code)


class SendProof(unittest.TestCase):

    def before(self):
        return [msg("Jane Example", "hello", "u1"), msg(ME, "Hi Jane, thanks.", "u2")]

    def test_a_new_message_from_us_with_this_text_is_proof(self):
        after = self.before() + [msg(ME, "Hi Jane, see you Thursday.", "u3")]
        self.assertIsNone(M.send_proof(self.before(), after, ME, "Hi Jane, see you Thursday."))

    def test_the_bubble_collapses_line_breaks_and_still_matches(self):
        after = self.before() + [msg(ME, "Hi Jane, see you Thursday.", "u3")]
        self.assertIsNone(M.send_proof(self.before(), after, ME,
                                       "Hi Jane,\n\nsee you Thursday."))

    def test_an_old_matching_message_is_not_proof(self):
        before = self.before()
        self.assertIsNotNone(M.send_proof(before, before, ME, "Hi Jane, thanks."))

    def test_their_message_with_our_text_is_not_proof(self):
        after = self.before() + [msg("Jane Example", "Hi Jane, see you.", "u3")]
        self.assertIsNotNone(M.send_proof(self.before(), after, ME, "Hi Jane, see you."))

    def test_a_different_last_message_is_not_proof(self):
        after = self.before() + [msg(ME, "something else", "u3")]
        self.assertIsNotNone(M.send_proof(self.before(), after, ME, "Hi Jane, see you."))

    def test_no_urn_is_not_proof(self):
        after = self.before() + [msg(ME, "Hi Jane, see you.", "")]
        self.assertIsNotNone(M.send_proof(self.before(), after, ME, "Hi Jane, see you."))

    def test_nothing_from_us_is_not_proof(self):
        self.assertIsNotNone(M.send_proof([], [msg("X Y", "hi", "u1")], ME, "hi"))


class Attribution(unittest.TestCase):
    """Review defect 2: whose message is whose must be positive, or refuse."""

    def test_us_and_them_only(self):
        msgs = [msg("Jane Example", "hi", "u1"), msg(ME, "hello", "u2")]
        self.assertIsNone(M.problem_in(msgs, ME, "Jane Example"))

    def test_a_third_name_refuses(self):
        """The signed-in name and the name on our messages differ: ours()
        would find nothing and already-sent would never fire."""
        msgs = [msg("Jane Example", "hi", "u1"), msg("Owner P.", "hello", "u2")]
        self.assertIsNotNone(M.problem_in(msgs, ME, "Jane Example"))

    def test_a_missing_urn_refuses(self):
        msgs = [msg("Jane Example", "hi", "u1"), msg(ME, "hello", "")]
        self.assertIsNotNone(M.problem_in(msgs, ME, "Jane Example"))

    def test_a_blank_sender_refuses(self):
        msgs = [msg("", "hi", "u1")]
        self.assertIsNotNone(M.problem_in(msgs, ME, "Jane Example"))

    def test_no_messages_refuses(self):
        self.assertIsNotNone(M.problem_in([], ME, "Jane Example"))


class AlreadySent(unittest.TestCase):

    def test_last_from_us_is_what_counts(self):
        msgs = [msg(ME, "first", "u1"), msg("Jane Example", "reply", "u2")]
        self.assertEqual(M.last_ours_text(msgs, ME), "first")
        self.assertTrue(M.same_text(M.last_ours_text(msgs, ME), "first"))

    def test_nothing_from_us(self):
        self.assertIsNone(M.last_ours_text([msg("A B", "x", "u1")], ME))
        self.assertFalse(M.same_text(None, "x"))

    def test_an_empty_name_matches_nobody(self):
        self.assertEqual(M.ours([msg("", "x", "u1")], ""), [])


class EmptyComposer(unittest.TestCase):

    def st(self, text, disabled, editors=1):
        return {"editors": editors, "editor_text": text, "send_disabled": disabled}

    def test_blank_and_disabled_is_empty(self):
        self.assertTrue(M.editor_is_empty(self.st("\n", True)))

    def test_blank_text_with_send_enabled_is_not_empty(self):
        self.assertFalse(M.editor_is_empty(self.st("", False)))

    def test_text_is_not_empty(self):
        self.assertFalse(M.editor_is_empty(self.st("Hi", True)))

    def test_unknown_send_state_is_not_empty(self):
        self.assertFalse(M.editor_is_empty(self.st("", None)))

    def test_two_editors_is_not_empty(self):
        self.assertFalse(M.editor_is_empty(self.st("", True, editors=2)))


class Text(unittest.TestCase):

    def test_line_endings_and_trailing_space(self):
        self.assertEqual(M.load_text("Hi Ann,  \r\n\r\nLine two.\r\n\r\n", None),
                         "Hi Ann,\n\nLine two.")

    def test_lines_of_keeps_blank_lines(self):
        self.assertEqual(M.lines_of("a\n\nb"), ["a", "", "b"])

    def test_a_file(self):
        fd, p = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            with io.open(p, "w", encoding="utf-8") as f:
                f.write("Hi Ann,\nsecond\n")
            self.assertEqual(M.load_text(None, p), "Hi Ann,\nsecond")
        finally:
            os.remove(p)

    def test_empty_refuses(self):
        with self.assertRaises(SystemExit):
            M.load_text("   \n ", None)

    def test_both_or_neither_refuses(self):
        with self.assertRaises(SystemExit):
            M.load_text(None, None)
        with self.assertRaises(SystemExit):
            M.load_text("x", "f.txt")


class Target(unittest.TestCase):

    def test_thread_url(self):
        k, v = M.classify_target("https://www.linkedin.com/messaging/thread/2-abc==/")
        self.assertEqual(k, "thread")

    def test_the_new_draft_is_not_a_thread(self):
        with self.assertRaises(SystemExit):
            M.classify_target("https://www.linkedin.com/messaging/thread/new/")

    def test_profile_url_and_slug(self):
        self.assertEqual(M.classify_target("https://www.linkedin.com/in/someone-1/")[0], "profile")
        k, v = M.classify_target("someone-1")
        self.assertEqual((k, v), ("profile", "https://www.linkedin.com/in/someone-1/"))

    def test_a_ref_without_its_prefix_is_not_a_slug(self):
        """It fits the slug pattern, and would spend a capped view on whatever
        profile that string names (review finding 9)."""
        from cc_linkedin_kit import inbox as I
        ref = I.make_ref({"participant": "A B", "when": "Oct 1", "index": 3}, "all")
        with self.assertRaises(SystemExit):
            M.classify_target(ref[len(I.REF_PREFIX):])

    def test_ref(self):
        from cc_linkedin_kit import inbox as I
        ref = I.make_ref({"participant": "A B", "when": "Oct 1", "index": 3}, "all")
        k, v = M.classify_target(ref)
        self.assertEqual((k, v["p"]), ("ref", "A B"))

    def test_anything_else_refuses(self):
        for t in ("", "https://www.linkedin.com/feed/", "https://example.com/in/x/",
                  "two words"):
            with self.assertRaises(SystemExit):
                M.classify_target(t)


# ---------------------------------------------------------------- the page, faked
#
# The two layouts the compose route can show, as the page readers return them.
# FIRST_CONVERSATION is what CARD_JS, STATE_JS and MESSAGES_JS read off the live
# page on 2026-10-21 (devthrottle#4306), with the person replaced. HISTORY is the
# compose route onto a conversation that already holds messages.

WHO = "Pat Example"
SLUG = "pat-example"
CARD_FIRST = {"links": 1, "name": WHO, "href": "/in/%s/" % SLUG,
              "badges": ["1st degree connection"]}
EMPTY_STATE = {"editors": 1, "editor_text": "\n", "send_disabled": True, "pills": [WHO],
               "events": 0}
FIRST_CONVERSATION = {"list": {"found": False}, "cards": [CARD_FIRST], "state": EMPTY_STATE}
# On a conversation with history the same card sits INSIDE the list and links
# by member id, not by the vanity slug (measured 2026-10-21).
CARD_IN_HISTORY = dict(CARD_FIRST, href="https://www.linkedin.com/in/ACoAAAExampleMemberIdOfTheUsualLength0000")
HISTORY = {"list": {"found": True, "events": 2, "messages": [
              {"sender": ME, "text": "hello", "urn": "u1"},
              {"sender": WHO, "text": "hi back", "urn": "u2"}]},
           "cards": [CARD_IN_HISTORY], "state": dict(EMPTY_STATE, events=2)}


class FakePage(object):
    def __init__(self, layout):
        self.layout = layout

    def locator(self, sel):
        page = self

        class L(object):
            first = None

            def wait_for(self, **kw):
                if not page.layout["list"].get("found"):
                    raise RuntimeError("timed out waiting for %s" % sel)
        loc = L()
        loc.first = loc
        return loc

    def evaluate(self, js, arg=None):
        from cc_linkedin_kit import inbox as I
        if js == I.MESSAGES_JS:
            return self.layout["list"]
        if js == M.CARD_JS:
            return self.layout["cards"]
        if js == M.STATE_JS:
            return self.layout["state"]
        raise AssertionError("an unexpected page reader was evaluated")


class FakeBrowser(object):
    def __init__(self, layout):
        self.page = FakePage(layout)

    def screenshot(self, path):
        raise AssertionError("no screenshot was asked for")


def history_of(layout, via="profile", slug=SLUG):
    """Run.history on a faked page: (messages, None) or (None, the FAIL line)."""
    from unittest import mock
    run = M.Run(FakeBrowser(layout), pace=None)
    run.via, run.slug, run.phase = via, slug, M.OPEN
    out = io.StringIO()
    with mock.patch.object(M.time, "sleep"), contextlib.redirect_stdout(out):
        try:
            return run.history(ME, WHO, "before typing"), None
        except SystemExit:
            return None, out.getvalue()


class FirstConversation(unittest.TestCase):
    """devthrottle#4306. A 1st-degree connection nobody has written to renders
    NO message list on the compose route. That layout must stage - recognised
    by what it SHOWS, the recipient's card - and an absent list with no such
    card must still fail as the moved selector it almost always is."""

    def test_the_first_conversation_layout_is_an_empty_history(self):
        got, why = history_of(FIRST_CONVERSATION)
        self.assertIsNone(why)
        self.assertEqual(got, [])

    def test_a_conversation_with_history_is_still_read(self):
        got, why = history_of(HISTORY)
        self.assertIsNone(why)
        self.assertEqual([m["urn"] for m in got], ["u1", "u2"])

    def test_no_list_and_no_card_fails(self):
        got, why = history_of(dict(FIRST_CONVERSATION, cards=[]))
        self.assertIsNone(got)
        self.assertIn("not positively a first conversation", why)
        self.assertIn("0 one-to-one profile cards", why)

    def test_an_existing_conversation_whose_list_selector_moved_fails(self):
        """The list is there but no longer matched: its card is still on the
        page, and must not pass the conversation off as a first one."""
        got, why = history_of(dict(HISTORY, list={"found": False}))
        self.assertIsNone(got)
        self.assertIn("not to the profile this run came from", why)

    def test_message_events_on_the_page_fail_even_with_a_matching_card(self):
        """A second presence that does not rest on the link's shape: should the
        in-list card ever link by vanity slug, the event count still refuses."""
        got, why = history_of(dict(HISTORY, list={"found": False}, cards=[CARD_FIRST]))
        self.assertIsNone(got)
        self.assertIn("2 message events", why)

    def test_a_run_from_a_member_id_profile_address_gets_no_card_path(self):
        member = "acoaaaexamplememberidoftheusuallength0000"
        card = dict(CARD_FIRST, href="https://www.linkedin.com/in/ACoAAAExampleMemberIdOfTheUsualLength0000")
        self.assertIn("not a vanity slug", M.card_problem([card], WHO, member))
        got, why = history_of(dict(FIRST_CONVERSATION, cards=[card]), slug=member)
        self.assertIsNone(got)
        self.assertIn("not a vanity slug", why)

    def test_a_list_with_no_events_is_not_an_empty_history_on_its_own(self):
        """Re-review finding: list found, zero events read out of it, is what an
        existing conversation looks like when the event selector is renamed.
        It used to pass with no other check."""
        empty_list = {"found": True, "events": 0, "messages": []}
        for cards in ([], [CARD_IN_HISTORY]):
            got, why = history_of(dict(HISTORY, list=empty_list, cards=cards,
                                       state=dict(EMPTY_STATE)))
            self.assertIsNone(got, cards)
            self.assertIn("not positively a first conversation", why)

    def test_a_vanity_slug_that_starts_like_a_member_id_is_still_a_slug(self):
        card = dict(CARD_FIRST, href="/in/acoastal-pat/")
        self.assertIsNone(M.card_problem([card], WHO, "acoastal-pat"))

    def test_a_leave_draft_says_what_to_do(self):
        got, why = history_of(dict(FIRST_CONVERSATION, state=dict(
            EMPTY_STATE, editor_text="the same text", send_disabled=False)))
        self.assertIn("--leave run", why)

    def test_after_typing_no_list_does_not_prove_nothing_was_sent(self):
        """The aftermath of a failed first-conversation run: no list then is
        NOT proof that nothing went (what a first send renders was never
        measured), so the run must say it could not check."""
        from unittest import mock
        run = M.Run(FakeBrowser(FIRST_CONVERSATION), pace=None)
        run.via, run.slug, run.who, run.phase = "profile", SLUG, WHO, M.OPEN
        with mock.patch.object(M.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run.history(ME, WHO, "before typing"), [])
            self.assertIsNone(run.new_since_before())

    def test_the_card_is_only_accepted_on_the_profile_route(self):
        got, why = history_of(FIRST_CONVERSATION, via="thread")
        self.assertIsNone(got)
        self.assertIn("no readable message list", why)

    def test_a_draft_in_the_composer_fails(self):
        got, why = history_of(dict(FIRST_CONVERSATION, state=dict(
            EMPTY_STATE, editor_text="words", send_disabled=False)))
        self.assertIsNone(got)
        self.assertIn("composer is not positively empty", why)

    def test_a_card_for_another_profile_fails(self):
        got, why = history_of(FIRST_CONVERSATION, slug="someone-else")
        self.assertIsNone(got)
        self.assertIn("not to the profile this run came from", why)

    def test_each_part_of_the_card_is_required(self):
        bad = {
            "two cards": [CARD_FIRST, CARD_FIRST],
            "no link": [dict(CARD_FIRST, links=0, name="", href="")],
            "two links": [dict(CARD_FIRST, links=2, name="", href="")],
            "another name": [dict(CARD_FIRST, name="Pat Examples")],
            "2nd degree": [dict(CARD_FIRST, badges=["2nd degree connection"])],
            "no badge": [dict(CARD_FIRST, badges=[])],
        }
        for what, cards in bad.items():
            self.assertIsNotNone(M.card_problem(cards, WHO, SLUG), what)
        self.assertIsNone(M.card_problem([CARD_FIRST], WHO, SLUG))

    def test_no_known_profile_fails(self):
        self.assertIsNotNone(M.card_problem([CARD_FIRST], WHO, ""))
        self.assertIsNotNone(M.card_problem([CARD_FIRST], WHO, None))

    def test_the_slug_is_compared_decoded_and_folded(self):
        self.assertEqual(M.profile_slug("https://www.linkedin.com/in/Pat-Example/?x=1"),
                         "pat-example")
        self.assertEqual(M.profile_slug("/in/j%C3%B8rgen-x/"), u"j\u00f8rgen-x")
        self.assertEqual(M.profile_slug("/messaging/compose/"), "")


class OneName(unittest.TestCase):
    """devthrottle#4339. The top card printed 'First (Maiden) Last' and the
    conversation 'First Last', and --expect-name was compared EXACTLY to each,
    so no value could pass both. One rule now names one person on every
    surface: drop a parenthetical, and otherwise stay exact."""

    def test_the_parenthetical_is_the_same_person(self):
        for expect in ("Ann (Maiden) Example", "Ann Example"):
            self.assertTrue(M.same_name(expect, "Ann (Maiden) Example"), expect)
            self.assertTrue(M.same_name(expect, "Ann Example"), expect)

    def test_it_is_not_a_substring_match(self):
        self.assertFalse(M.same_name("Ann", "Joanne Example"))
        self.assertFalse(M.same_name("Ann Example", "Ann Examples"))
        self.assertFalse(M.same_name("Ann Example", "Ann B Example"))
        self.assertFalse(M.same_name("Ann Example", "Example Ann"))

    def test_nothing_else_is_folded(self):
        self.assertFalse(M.same_name("ann example", "Ann Example"))
        self.assertFalse(M.same_name(u"Ren\u00e9 Example", "Rene Example"))

    def test_a_name_that_is_only_a_parenthetical_matches_nobody(self):
        self.assertFalse(M.same_name("(Maiden)", ""))
        self.assertFalse(M.same_name("(Maiden)", "(Other)"))
        self.assertFalse(M.same_name("", ""))

    def test_every_name_check_in_the_verb_uses_the_one_rule(self):
        with io.open(M.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("same_person(", src)
        self.assertGreaterEqual(src.count("same_name(expect"), 3)

    def test_senders_are_attributed_by_the_same_rule(self):
        """A sender printed with the parenthetical the pill omits is still the
        participant, and ours are still ours."""
        msgs = [msg(ME, "a", "u1"), msg("Ann (Maiden) Example", "b", "u2")]
        self.assertIsNone(M.problem_in(msgs, ME, "Ann Example"))
        self.assertEqual(len(M.ours(msgs, ME)), 1)
        self.assertIsNotNone(M.problem_in(msgs + [msg("Ann Examples", "c", "u3")],
                                          ME, "Ann Example"))

    def test_the_aftermath_knows_their_message_by_the_same_rule(self):
        """A new message from the participant, printed with the parenthetical
        the pill omits, is theirs - not 'SOMETHING MAY HAVE BEEN SENT'."""
        from unittest import mock
        layout = dict(HISTORY, list={"found": True, "events": 3, "messages": [
            msg(ME, "hello", "u1"), msg("Pat (Maiden) Example", "hi back", "u2"),
            msg("Pat (Maiden) Example", "and another", "u3")]})
        run = M.Run(FakeBrowser(layout), pace=None)
        run.who, run.phase = WHO, M.TYPED
        run.before = [msg(ME, "hello", "u1"), msg(WHO, "hi back", "u2")]
        with mock.patch.object(M.time, "sleep"), \
                mock.patch.object(run, "clear_quietly", return_value=True):
            said = run.aftermath()
        self.assertIn("Nothing from us was sent", said)
        self.assertNotIn("MAY HAVE", said)

    def test_the_profile_route_takes_either_form(self):
        """open_profile against a faked top card that prints the parenthetical."""
        for expect in ("Ann (Maiden) Example", "Ann Example"):
            run, why = open_profile_with("Ann (Maiden) Example", expect)
            self.assertIsNone(why, expect)
            self.assertEqual((run.via, run.slug), ("profile", "ann-example"))

    def test_the_profile_route_still_refuses_another_person(self):
        run, why = open_profile_with("Ann (Maiden) Example", "Anna Example")
        self.assertIn("top card names", why)


def open_profile_with(card_name, expect):
    """Run.open_profile on a faked profile page: (run, None) or (run, FAIL line)."""
    from cc_linkedin_kit import people as P
    href = "/messaging/compose/?profileUrn=urn%3Ali%3Afsd_profile%3AX&recipient=X"
    card = {"name": card_name, "degrees": [u"\u00b7 1st"],
            "controls": [{"tag": "A", "text": "Message", "href": href}]}

    class Page(object):
        url = "https://www.linkedin.com/in/ann-example/"

        def evaluate(self, js, arg=None):
            assert js == P.TOPCARD_JS
            return card

    class Br(object):
        page = Page()

        def read(self, url, where, settle=6):
            return "https://www.linkedin.com/in/ann-example/?isSelfProfile=false"

    class Pace(object):
        def before_view(self, what):
            pass

        def after_view(self):
            pass

    run = M.Run(Br(), Pace())
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            run.open_profile("https://www.linkedin.com/in/ann-example/", expect)
            return run, None
        except SystemExit:
            return run, out.getvalue()


if __name__ == "__main__":
    unittest.main()
