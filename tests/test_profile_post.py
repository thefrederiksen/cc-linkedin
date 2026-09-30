# -*- coding: utf-8 -*-
"""`post --profile` and `--hand-over`: who the post is written as, and what may
be combined with it.

The member's composer is measured only up to the moment before Post
(docs/profile-post-survey-2026-09-30.md), so everything past that point must
REFUSE rather than run unproven. Each case below is a refusal a caller could
otherwise walk straight past.
"""
import argparse
import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cc_linkedin as tool


def args(**kw):
    base = dict(page=None, page_name=None, profile=None, schedule=None, submit=False,
                hand_over=False)
    base.update(kw)
    return argparse.Namespace(**base)


class PostTarget(unittest.TestCase):

    def refuses(self, a, words):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            tool.post_target(a)
        self.assertIn("FAIL", out.getvalue())
        self.assertIn(words, out.getvalue())

    def test_neither_page_nor_profile_refuses(self):
        self.refuses(args(), "exactly one")

    def test_both_page_and_profile_refuse(self):
        self.refuses(args(page="1", page_name="P", profile="Soren Frederiksen"), "exactly one")

    def test_page_without_page_name_refuses(self):
        self.refuses(args(page="1"), "--page-name")

    def test_profile_with_page_name_refuses(self):
        self.refuses(args(profile="Soren Frederiksen", page_name="P"), "--page-name")

    def test_profile_submit_is_not_built(self):
        self.refuses(args(profile="Soren Frederiksen", submit=True), "NOT BUILT")

    def test_profile_schedule_is_not_built(self):
        self.refuses(args(profile="Soren Frederiksen", schedule="2026-10-01 09:00"), "schedule")

    def test_submit_and_hand_over_contradict(self):
        self.refuses(args(page="1", page_name="P", submit=True, hand_over=True), "contradict")

    def test_profile_stage_and_hand_over_are_allowed(self):
        tool.post_target(args(profile="Soren Frederiksen"))
        tool.post_target(args(profile="Soren Frederiksen", hand_over=True))

    def test_page_paths_unchanged(self):
        tool.post_target(args(page="1", page_name="P"))
        tool.post_target(args(page="1", page_name="P", submit=True))
        tool.post_target(args(page="1", page_name="P", hand_over=True))


class ProfileComposerHasItsOwnDom(unittest.TestCase):
    """The Page composer's selectors are blind on the member's native <dialog>;
    the Profile class must not inherit them for anything that touches the DOM."""

    def test_dom_methods_are_overridden(self):
        for name in ("buttons", "composer_open", "live_dialog", "editor_text", "dialog",
                     "open_composer", "ensure_empty_composer", "discard", "attach",
                     "media_still_attached", "type_text", "screenshot"):
            self.assertIn(name, tool.Profile.__dict__, name)


if __name__ == "__main__":
    unittest.main()
