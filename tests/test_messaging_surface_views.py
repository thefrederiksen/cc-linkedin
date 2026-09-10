# -*- coding: utf-8 -*-
"""A2: the messaging LIST and the invitation manager are our own surfaces. A
THREAD is not.

`docs/phase-3-amendments.md` A2, ruled by the Architect on 2026-09-10 after the
survey measured that `/messaging/`, `/messaging/thread/<id>/` and
`/mynetwork/invitation-manager/` all counted as capped `view` - because
`surface_kind` recognised exactly three own-surfaces and everything else fell
through to the safety number.

THE SPLIT IS THE WHOLE POINT AND IT IS NOT ARBITRARY. The cap exists against
activity that looks automated to LinkedIn AND reaches other people
(`docs/ruling-view-cap-2026-09-09.md`).

  * `/messaging/` - the owner's own inbox. Notifies nobody. No volume of reading
    it resembles scraping. UNCAPPED.
  * `/mynetwork/invitation-manager/...` - the owner's own invitations, sent and
    received. Same reasoning. UNCAPPED.
  * `/messaging/thread/<id>/` - CAPPED, and not because it looks like scraping.
    Opening a thread marks it read and can show the other participant a read
    receipt. It is the one messaging read with an outward, irreversible side
    effect, so it stays on the safety number: a runaway loop meets a wall
    instead of quietly marking a hundred conversations read.

So the test that matters most in this file is the thread one. A classifier that
got the two easy cases right and let a thread through would satisfy the letter
of A2 and destroy its reason.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit.browser import surface_kind


class TheMessagingListIsOurs(unittest.TestCase):

    def test_the_plain_list(self):
        self.assertEqual(surface_kind("https://www.linkedin.com/messaging/"), "view_self")

    def test_without_the_trailing_slash(self):
        self.assertEqual(surface_kind("https://www.linkedin.com/messaging"), "view_self")

    def test_with_a_filter_on_the_query(self):
        self.assertEqual(surface_kind("https://www.linkedin.com/messaging/?filter=unread"),
                         "view_self")


class TheInvitationManagerIsOurs(unittest.TestCase):

    def test_the_bare_url(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/mynetwork/invitation-manager/"), "view_self")

    def test_the_received_tab(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/mynetwork/invitation-manager/received/"),
            "view_self")

    def test_the_sent_tab(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/mynetwork/invitation-manager/sent/"),
            "view_self")

    def test_the_sent_tabs_people_filter(self):
        """Measured on the live page: `People (40)` links to /sent/CONNECTION/."""
        self.assertEqual(
            surface_kind(
                "https://www.linkedin.com/mynetwork/invitation-manager/sent/CONNECTION/"),
            "view_self")


class AThreadIsNot(unittest.TestCase):
    """The half of A2 that costs something. If these pass by accident - because
    the messaging pattern was written as a prefix - A2 has been implemented
    backwards and the read-receipt wall is gone."""

    def test_a_thread_is_capped(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/thread/2-abc123def=="), "view")

    def test_a_thread_with_a_trailing_slash_is_capped(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/thread/2-abc123def==/"), "view")

    def test_the_compose_route_is_capped(self):
        """/messaging/compose/?profileUrn=... opens a draft against a real
        person and is where the survey did its thread work. Not the list."""
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/compose/?recipient=1234"), "view")

    def test_anything_else_under_messaging_is_capped(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/anything-new-linkedin-adds/"),
            "view")


class TheUnrecognisedDirectionIsStillTheCappedOne(unittest.TestCase):
    """The enumeration rule from the ruling, re-asserted on the two forms A2
    adds: positive match or nothing, and a near-miss is somebody else's."""

    def test_another_host_serving_the_same_path_is_capped(self):
        self.assertEqual(surface_kind("https://example.com/messaging/"), "view")
        self.assertEqual(
            surface_kind("https://example.com/mynetwork/invitation-manager/"), "view")

    def test_a_lookalike_host_is_capped(self):
        self.assertEqual(surface_kind("https://linkedin.com.evil.test/messaging/"), "view")

    def test_a_lookalike_path_is_capped(self):
        self.assertEqual(surface_kind("https://www.linkedin.com/messaging-beta/"), "view")
        self.assertEqual(
            surface_kind("https://www.linkedin.com/mynetwork/invitation-manager-v2/"), "view")

    def test_mynetwork_itself_is_capped(self):
        """/mynetwork/ is the suggestions grid - other people's faces. It is not
        the invitation manager and A2 does not name it."""
        self.assertEqual(surface_kind("https://www.linkedin.com/mynetwork/"), "view")

    def test_our_own_path_hidden_in_somebody_elses_query_is_capped(self):
        """The failure mode of a classifier that searches the whole URL string
        instead of its path."""
        self.assertEqual(
            surface_kind("https://www.linkedin.com/in/somebody/?next=//www.linkedin.com/messaging/"),
            "view")

    def test_the_subdomain_form_is_still_ours(self):
        self.assertEqual(surface_kind("https://uk.linkedin.com/messaging/"), "view_self")


class WhatWasAlreadyTrueStaysTrue(unittest.TestCase):
    """A2 adds two surfaces. It must not disturb the three the earlier ruling
    settled, nor the default."""

    def test_the_owners_own_profile(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/in/sorenfrederiksen/"), "view_self")

    def test_a_strangers_profile(self):
        self.assertEqual(surface_kind("https://www.linkedin.com/in/somebody-else/"), "view")

    def test_notifications(self):
        self.assertEqual(surface_kind("https://www.linkedin.com/notifications/"), "view_self")

    def test_nothing_at_all(self):
        self.assertEqual(surface_kind(None), "view")
        self.assertEqual(surface_kind(""), "view")


if __name__ == "__main__":
    unittest.main()
