# -*- coding: utf-8 -*-
"""R5: can_connect fails rather than guesses, in both directions.

From `docs/inspection-slice-3-verbs.md`, finding 3. A value that means "you can
invite this person" must never come from a code path that did not positively see
an invite control, and "you cannot" must never come from a path that merely
failed to look properly.

Three of the four concrete cases the inspector named are DECISIONS and are
tested here. The fourth - the page-global menu query letting an unrelated menu
supply the item that proves this menu rendered - is a DOM scope change; it is
implemented (MENU_JS reads inside the one visible [role=menu] and refuses when
there is not exactly one) and it is NOT covered here, because proving it needs a
page with two open menus. Said out loud rather than left to look covered.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import people as P

INVITE = {"text": "Connect", "aria": "Invite A Person to connect",
          "href": "/preload/custom-invite/?vanityName=aperson", "disabled": False}
MESSAGE = {"text": "Message", "aria": "", "href": "", "disabled": False}
FOLLOW = {"text": "Follow", "aria": "", "href": "", "disabled": False}


class TheInviteControlIsIdentifiedNotGuessed(unittest.TestCase):

    def test_the_invite_control_is_found_by_its_href(self):
        got = P._invite([MESSAGE, INVITE, FOLLOW])
        self.assertIs(got, INVITE)

    def test_the_invite_control_is_found_by_its_label(self):
        by_label = {"text": "Connect", "aria": "Invite A Person to connect", "href": "",
                    "disabled": False}
        self.assertIs(P._invite([MESSAGE, by_label]), by_label)

    def test_the_bare_word_connect_is_not_an_invite_control(self):
        # It is all over a profile page - the right-hand rail's suggestion cards
        # are full of it.
        rail = {"text": "Connect", "aria": "", "href": "/in/somebody-else/", "disabled": False}
        self.assertIsNone(P._invite([MESSAGE, rail]))

    def test_no_invite_control_at_all(self):
        self.assertIsNone(P._invite([MESSAGE, FOLLOW]))


class ADisabledControlIsNotAnAnswer(unittest.TestCase):
    """The enabled state was never checked. A busy or disabled Connect control
    that kept its href was reported as can_connect: true."""

    def test_an_enabled_invite_control_says_yes_and_where(self):
        can, reason, via, url = P._decide(INVITE, "on the top card", "topcard")
        self.assertIs(can, True)
        self.assertEqual(via, "topcard")
        self.assertIn("custom-invite", url)
        self.assertTrue(reason)

    def test_a_disabled_invite_control_is_undecided_with_a_reason(self):
        can, reason, via, url = P._decide(dict(INVITE, disabled=True),
                                          "on the top card", "topcard")
        self.assertIsNone(can, "a control the page has disabled is not a yes")
        self.assertIsNone(via, "and it hands out no invitation")
        self.assertIsNone(url)
        self.assertIn("disabled", reason)
        self.assertIn("not the same answer as no invite control", reason)

    def test_an_aria_disabled_control_counts_as_disabled(self):
        # This is what the topcard JS reports for aria-disabled="true".
        can, _, _, _ = P._decide(dict(INVITE, disabled=True), "in the More menu", "more-menu")
        self.assertIsNone(can)

    def test_no_control_decides_nothing_and_says_so_by_returning_nothing(self):
        # _decide is only ever handed a control it found; None means "keep
        # looking", never "the answer is no".
        self.assertIsNone(P._decide(None, "on the top card", "topcard"))

    def test_a_true_can_connect_always_carries_where_and_how(self):
        # The invariant the self-test asserts, at its source: a yes is only ever
        # produced with the control in hand.
        can, reason, via, url = P._decide(INVITE, "in the More menu", "more-menu")
        self.assertIs(can, True)
        self.assertEqual(via, "more-menu")
        self.assertTrue(url and "custom-invite" in url)


class TheMenuIsGivenTimeToStopChanging(unittest.TestCase):
    """The split-render case: a menu that renders its proof item at 1.5 seconds
    and its Connect item at 1.8 passed the old flat sleep, and the verb then
    believed an absence it had read too early."""

    def test_the_settle_window_is_longer_than_the_old_flat_sleep(self):
        self.assertGreater(P.MENU_SETTLE_SECONDS, 1.5)
        self.assertGreater(P.MENU_SETTLE_SECONDS / P.MENU_READ_GAP, 2,
                           "there must be room for at least two reads to compare")

    def test_the_menu_read_asks_for_the_enabled_state_and_the_menu_count(self):
        # The shape of what MENU_JS returns is what _settled_menu compares and
        # what _connect refuses on, so it is worth asserting it did not drift.
        for needed in ("role=menu", "menus", "items", "disabled"):
            self.assertIn(needed, P.MENU_JS)


if __name__ == "__main__":
    unittest.main()
