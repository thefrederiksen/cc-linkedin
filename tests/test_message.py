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


if __name__ == "__main__":
    unittest.main()
