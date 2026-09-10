# -*- coding: utf-8 -*-
"""F2: `notifications` and `stats` register a view of our own surface.

THE DEFECT. Both verbs opened a real page in the signed-in browser and counted
nothing at all - not even `view_self`. They are our own screens, so they are
correctly OUTSIDE the safety cap; but the whole point of the `view_self` track,
in the ruling that created it, is that `pace.json` shows everything this toolkit
opened, so that a runaway loop is visible and so that the file can be reconciled
against a run's own registry. A surface that appears nowhere reconciles against
nothing.

The ruling names "the owner's own profile, and a Page he administers" and does
not mention these two, which is why the live-proving Manager raised it instead
of widening it on its own authority. The Architect then ruled: both register
`view_self`.

STATS IS THE ONE WITH A TRAP IN IT. `--page` is an argument, so the Page it is
pointed at is not necessarily one the owner administers. The uncapped counter
must never be reachable by asking for it, so `stats` registers `view_self` only
when the Page id is positively on the owner's own list, and `view` - capped -
otherwise. That mirrors `read_company`, which had the same problem and solved it
the same way.

No browser and no network: both verbs are driven with a stub Browser whose
`read` raises, so what is asserted is what was registered AT THE MOMENT the
navigation was attempted.
"""
import argparse
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import account as A
from cc_linkedin_kit import browser as B


class Navigated(Exception):
    """Raised by the stub in place of actually opening the page."""


class StubBrowser(object):

    def __init__(self, seen):
        self.seen = seen

    def __call__(self, port):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, url, where, settle=6):
        self.seen.append([dict(v) for v in B.views_registered()])
        raise Navigated(url)


class OwnSurfaceCase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cc-linkedin-own-")
        self._state = B.STATE_DIR
        B.STATE_DIR = self.dir
        self._gap = B.Pace.VIEW_GAP
        B.Pace.VIEW_GAP = (0, 0)
        self._browser = A.Browser
        del B._VIEWS[:]

    def tearDown(self):
        B.STATE_DIR = self._state
        B.Pace.VIEW_GAP = self._gap
        A.Browser = self._browser
        del B._VIEWS[:]
        shutil.rmtree(self.dir, ignore_errors=True)

    def drive(self, verb, **kw):
        """Run one verb until it tries to navigate. Returns the registry as it
        stood at that moment."""
        seen = []
        A.Browser = StubBrowser(seen)
        args = argparse.Namespace(port=9224, **kw)
        try:
            verb(args)
        except Navigated:
            pass
        else:
            self.fail("the verb never navigated")
        return seen[0]


class NotificationsAreCountedAsOurOwn(OwnSurfaceCase):

    def test_it_registers_a_view_before_it_opens_the_page(self):
        at_navigation = self.drive(A.notifications, limit=25)
        self.assertEqual(len(at_navigation), 1,
                         "notifications used to open its page and count nothing")

    def test_it_is_on_the_self_counter_and_not_the_capped_one(self):
        at_navigation = self.drive(A.notifications, limit=25)
        self.assertEqual(at_navigation[0]["kind"], "view_self")
        self.assertEqual(B.Pace().count("view"), 0,
                         "our own notifications page must not spend the safety number")
        self.assertEqual(B.Pace().count("view_self"), 1)

    def test_the_registry_says_what_was_opened(self):
        at_navigation = self.drive(A.notifications, limit=25)
        self.assertIn("notification", at_navigation[0]["what"].lower())

    def test_it_is_not_capped(self):
        """VIEW_SELF_CAP is None, so a loop on our own notifications is counted
        and never refused. Asserted here because F2 is what puts this verb on
        that counter."""
        for _ in range(B.Pace.VIEW_CAP + 5):
            B.Pace().before_self_view("our own notifications")
            B.Pace().after_view()
        self.assertEqual(B.Pace().count("view_self"), B.Pace.VIEW_CAP + 5)


class StatsIsCountedAsOursOnlyWhenItIsOurs(OwnSurfaceCase):

    def test_our_own_page_is_a_self_view(self):
        page = sorted(B.OWN_PAGE_KEYS)[0]
        at_navigation = self.drive(A.stats, page=page, page_name=None, days=30)
        self.assertEqual(len(at_navigation), 1, "stats used to count nothing at all")
        self.assertEqual(at_navigation[0]["kind"], "view_self")
        self.assertEqual(B.Pace().count("view"), 0)

    def test_our_own_page_by_slug_is_also_a_self_view(self):
        at_navigation = self.drive(A.stats, page="centerconsulting-inc", page_name=None,
                                   days=30)
        self.assertEqual(at_navigation[0]["kind"], "view_self")

    def test_somebody_elses_page_id_is_a_capped_view(self):
        """The uncapped counter is not reachable by naming a Page. A --page we
        do not administer will fail on the landing assertions a moment later,
        but the view has already been taken by then and it is charged to the
        safety number."""
        at_navigation = self.drive(A.stats, page="999999", page_name=None, days=30)
        self.assertEqual(at_navigation[0]["kind"], "view")
        self.assertEqual(B.Pace().count("view"), 1)
        self.assertEqual(B.Pace().count("view_self"), 0)

    def test_the_registry_names_the_page_that_was_asked_for(self):
        page = sorted(B.OWN_PAGE_KEYS)[0]
        at_navigation = self.drive(A.stats, page=page, page_name=None, days=30)
        self.assertIn(page, at_navigation[0]["what"])


class NeitherVerbSpendsTheSafetyNumber(OwnSurfaceCase):
    """The reason this is safe to do at all: F2 adds two views per selftest run
    and NONE of them to the capped counter."""

    def test_a_run_of_both_leaves_the_capped_counter_where_it_was(self):
        self.drive(A.notifications, limit=25)
        del B._VIEWS[:]
        self.drive(A.stats, page=sorted(B.OWN_PAGE_KEYS)[0], page_name=None, days=30)
        self.assertEqual(B.Pace().count("view"), 0)
        self.assertEqual(B.Pace().count("view_self"), 2)


if __name__ == "__main__":
    unittest.main()
