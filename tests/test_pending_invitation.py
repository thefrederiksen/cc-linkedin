# -*- coding: utf-8 -*-
"""F3: a pending invitation is reported as a pending invitation.

THE DEFECT. On a profile with an invitation already outstanding, `read-profile`
answered `can_connect: false` - correct - with the reason "no invite control on
the top card and none in the More menu", which is true and is not what the page
said. The card plainly reads Pending. A right answer with a wrong reason is how
the next reader spends an hour in the wrong place, and R5 already says a field
must name what it SAW rather than what it failed to find.

MEASURED, 2026-09-10, on the profile the Architect sent a real invitation to the
day before - through `tools/survey.py`, at a cost of one capped view, because
the last time somebody in this mission reasoned about what LinkedIn probably
renders instead of looking, the result was R1.2 and it was wrong. The control is
an anchor in the top card's action row, beside Message and More:

    text        "Pending"
    aria-label  "Pending, click to withdraw invitation sent to <the person>"
    href        the profile's own URL - NOT a withdraw endpoint
    disabled    false; the FILLED control on that row is Message

So the matcher is the aria-label, and the bare word "Pending" is not enough on
its own - the same rule `_invite` applies to the bare word "Connect", and for
the same reason: precision matters more than recall here. A false positive
tells Phase 3's `withdraw` there is an invitation to withdraw when there is
none. A false negative gives back the uninformative-but-true answer we started
with, which is where this began. The live row P2-11 is what stops a false
negative going unnoticed if LinkedIn changes that label.

No browser and no network: `_connect` is handed a card and, on the pending path,
never reaches for one - which is itself asserted below by passing `br=None`.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import people as P
from cc_linkedin_kit import selectors as S

# Exactly as measured, with the person's name replaced.
PENDING = {"text": "Pending",
           "aria": "Pending, click to withdraw invitation sent to A Person",
           "href": "https://www.linkedin.com/in/aperson/", "disabled": False,
           "filled": False}
MESSAGE = {"text": "Message", "aria": "", "href": "/messaging/compose/?profileUrn=urn",
           "disabled": False, "filled": True}
MORE = {"text": "More", "aria": "", "href": "", "disabled": False, "filled": False}
INVITE = {"text": "Connect", "aria": "Invite A Person to connect",
          "href": "/preload/custom-invite/?vanityName=aperson", "disabled": False}


def card(controls):
    return {"controls": controls}


class ThePendingControlIsIdentifiedNotGuessed(unittest.TestCase):

    def test_the_pending_control_is_found_by_its_label(self):
        self.assertIs(P._pending([MESSAGE, PENDING, MORE]), PENDING)

    def test_a_card_with_no_pending_control_has_none(self):
        self.assertIsNone(P._pending([MESSAGE, INVITE, MORE]))

    def test_the_bare_word_pending_is_not_a_pending_invitation(self):
        """It is a word that turns up on a profile - a verification chip, an
        experience entry. The label is what was measured and the label is what
        is matched."""
        bare = {"text": "Pending", "aria": "", "href": "", "disabled": False}
        self.assertIsNone(P._pending([MESSAGE, bare, MORE]))

    def test_an_empty_control_list_has_no_pending_control(self):
        self.assertIsNone(P._pending([]))


class APendingInvitationIsReportedAsOne(unittest.TestCase):
    """`_connect` on the measured card. `br` is None on purpose: if the pending
    path ever reaches for the browser to open the More menu, this raises rather
    than passing."""

    def decide(self, controls, degree="2nd"):
        return P._connect(None, card(controls), "A Person", degree)

    def test_can_connect_is_false_not_null(self):
        can_connect = self.decide([MESSAGE, PENDING, MORE])[0]
        self.assertIs(can_connect, False,
                      "an outstanding invitation is a definite no, not an unknown")

    def test_the_reason_names_the_pending_state(self):
        reason = self.decide([MESSAGE, PENDING, MORE])[1]
        self.assertIn("pending", reason.lower())
        self.assertNotIn("no invite control", reason,
                         "that is the uninformative reason this replaces")

    def test_it_hands_out_no_invitation_url(self):
        _, _, via, url = self.decide([MESSAGE, PENDING, MORE])[:4]
        self.assertIsNone(via)
        self.assertIsNone(url)

    def test_invitation_pending_is_true(self):
        self.assertIs(self.decide([MESSAGE, PENDING, MORE])[4], True)

    def test_the_pending_path_never_opens_the_more_menu(self):
        # br=None throughout: reaching the menu would be an AttributeError.
        self.decide([MESSAGE, PENDING, MORE])

    def test_a_profile_we_can_invite_is_not_pending(self):
        can, _, via, url, pending = self.decide([MESSAGE, INVITE, MORE])
        self.assertIs(can, True)
        self.assertEqual(via, "topcard")
        self.assertTrue(url)
        self.assertIs(pending, False)

    def test_our_own_profile_is_not_pending(self):
        can, reason, via, url, pending = self.decide([MORE], degree="self")
        self.assertIsNone(can)
        self.assertIs(pending, False)
        self.assertIn("own profile", reason)

    def test_pending_wins_over_an_invite_control_on_the_same_card(self):
        """A card cannot carry both - LinkedIn paints Connect or Pending, not
        both. If one ever does, the answer that acts on nobody wins."""
        can, _, _, _, pending = self.decide([MESSAGE, INVITE, PENDING, MORE])
        self.assertIs(can, False)
        self.assertIs(pending, True)


class ThePendingLabelIsTheMeasuredOne(unittest.TestCase):

    def test_the_selector_matches_what_the_live_page_carried(self):
        self.assertTrue(S.INVITE_PENDING_ARIA.match(
            "Pending, click to withdraw invitation sent to A Person"))

    def test_the_selector_does_not_match_a_bare_pending(self):
        self.assertFalse(S.INVITE_PENDING_ARIA.match("Pending"))

    def test_the_selector_does_not_match_an_invite_label(self):
        self.assertFalse(S.INVITE_PENDING_ARIA.match("Invite A Person to connect"))


if __name__ == "__main__":
    unittest.main()
