# -*- coding: utf-8 -*-
"""Which surfaces are ours, by the test that a read receipt is somebody else's.

A2 (`docs/phase-3-amendments.md`, 2026-09-10) put `/messaging/` on the uncapped
counter because it is the owner's own inbox, and left `/messaging/compose/`
capped by not matching it. CORRECTED before 1.0: the letter and the reason
pointed opposite ways.

THE TEST IS NOT "IS THIS SURFACE MINE". It is "CAN LOADING IT CHANGE SOMETHING
ANOTHER PERSON CAN SEE." A read receipt is visible to somebody else, so a
surface that can raise one is capped no matter whose inbox it sits in. Ownership
was the wrong question: every surface here is the owner's, and they still do not
all cost the same.

Applied:

  * `/messaging/` - CAPPED. The list is the route believed to select a
    conversation into the reading pane, which marks it read. It is the owner's
    own inbox and that is not the point. Uncap it only when somebody has
    MEASURED that loading the bare list opens no conversation.
  * `/messaging/compose/` - UNCAPPED. Measured to open no conversation: it is an
    empty draft. Nothing is marked read and nobody is told it was loaded. Note
    that this is the exact reverse of what A2 shipped.
  * `/messaging/thread/<id>/` - CAPPED, unchanged. Opening a thread marks it
    read and can show the other participant a receipt. The plainest case.
  * `/mynetwork/invitation-manager/...` - UNCAPPED, unchanged. Sending an
    invitation is what another person sees; reading the list of ones already
    sent shows nobody anything.

The cases that matter most here are `/messaging/` and `/messaging/compose/`. A
classifier that has them the wrong way round satisfies "these are my own
surfaces" perfectly and spends the safety budget on the wrong one.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit.browser import surface_kind


class TheComposeRouteIsOurs(unittest.TestCase):
    """Uncapped because it opens no conversation, not because it is ours."""

    def test_compose_with_a_recipient_on_the_query(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/compose/?recipient=1234"),
            "view_self")

    def test_compose_bare(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/compose/"), "view_self")

    def test_compose_without_the_trailing_slash(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/compose"), "view_self")

    def test_the_subdomain_form_is_still_ours(self):
        self.assertEqual(
            surface_kind("https://uk.linkedin.com/messaging/compose/"), "view_self")


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


class AnythingThatCanRaiseAReadReceiptIsCapped(unittest.TestCase):
    """The half that costs something. Each of these is the owner's own surface
    and each is capped anyway, which is the whole correction."""

    def test_the_plain_list_is_capped(self):
        self.assertEqual(surface_kind("https://www.linkedin.com/messaging/"), "view")

    def test_the_list_without_a_trailing_slash_is_capped(self):
        self.assertEqual(surface_kind("https://www.linkedin.com/messaging"), "view")

    def test_the_list_with_a_filter_is_capped(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/?filter=unread"), "view")

    def test_a_thread_is_capped(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/thread/2-abc123def=="), "view")

    def test_a_thread_with_a_trailing_slash_is_capped(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/thread/2-abc123def==/"), "view")

    def test_anything_else_under_messaging_is_capped(self):
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/anything-new-linkedin-adds/"),
            "view")

    def test_a_thread_is_not_reached_by_the_compose_pattern(self):
        """The failure this guards: writing compose as a prefix, which would
        swallow every route under /messaging/ including the threads."""
        self.assertEqual(
            surface_kind("https://www.linkedin.com/messaging/compose/thread/2-abc=="), "view")


class TheUnrecognisedDirectionIsStillTheCappedOne(unittest.TestCase):
    """Positive match or nothing, and a near-miss is somebody else's."""

    def test_another_host_serving_the_same_path_is_capped(self):
        self.assertEqual(surface_kind("https://example.com/messaging/compose/"), "view")
        self.assertEqual(
            surface_kind("https://example.com/mynetwork/invitation-manager/"), "view")

    def test_a_lookalike_host_is_capped(self):
        self.assertEqual(
            surface_kind("https://linkedin.com.evil.test/messaging/compose/"), "view")

    def test_a_lookalike_path_is_capped(self):
        self.assertEqual(surface_kind("https://www.linkedin.com/messaging-beta/compose/"), "view")
        self.assertEqual(surface_kind("https://www.linkedin.com/messaging/composer/"), "view")
        self.assertEqual(
            surface_kind("https://www.linkedin.com/mynetwork/invitation-manager-v2/"), "view")

    def test_mynetwork_itself_is_capped(self):
        """/mynetwork/ is the suggestions grid - other people's faces."""
        self.assertEqual(surface_kind("https://www.linkedin.com/mynetwork/"), "view")

    def test_our_own_path_hidden_in_somebody_elses_query_is_capped(self):
        """The failure mode of a classifier that searches the whole URL string
        instead of its path."""
        self.assertEqual(
            surface_kind(
                "https://www.linkedin.com/in/somebody/?next=//www.linkedin.com/messaging/compose/"),
            "view")


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
