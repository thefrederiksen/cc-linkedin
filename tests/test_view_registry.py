# -*- coding: utf-8 -*-
"""F1: every view this toolkit takes is on the counter, and the counter says
exactly what it covers.

THE DEFECT. `tools/survey.py` drives `cc_linkedin_kit.browser.Browser` - the same lock, the
same background tab, the same real profile opened against the owner's account -
and registered nothing. Two profile views were taken that way on 2026-09-09
while `pace.json` sat at eighty, and both the Manager who took them and the
Architect who had done the same thing the night before missed it. A safety
counter with an uncounted path is not a safety counter.

TWO HALVES, and the second matters as much as the first:

  * the survey tool registers a view like every other read here, on the counter
    the surface belongs to. There is no exemption for "just looking" - LinkedIn
    cannot tell the difference and neither can the owner's account.
  * `Pace` stops claiming a scope it cannot deliver. It cannot see a profile
    opened by an agent hand-driving a browser, because that path never enters
    this code, so what it counts is "views taken through this toolkit" and it
    has to say so - in the docstring, in the README and in the skill, because
    the agent that opens a profile by hand reads one of those three and not the
    other two. R15 is the same lesson on the same file: an overstated guarantee
    is the sentence somebody relies on instead of checking.

No browser and no network: the survey tool is driven with a stub whose `goto`
raises, so what is asserted is what was registered AT THE MOMENT the navigation
was attempted.
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cc_linkedin_kit import browser as B

SKILL = os.path.join(ROOT, ".claude", "skills", "linkedin", "SKILL.md")
README = os.path.join(ROOT, "README.md")

# The two phrases that have to reach whoever is about to open a profile by hand.
# Written once here, asserted in all three places, so the three cannot drift.
SCOPE = "views taken through this toolkit"
HAND = "hand-driving a browser"


def _survey_tool():
    """tools/survey.py, loaded by path - `tools` is not a package."""
    spec = importlib.util.spec_from_file_location(
        "survey_tool_under_test", os.path.join(ROOT, "tools", "survey.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Navigated(Exception):
    """Raised by the stub in place of actually opening the page."""


class StubPage(object):
    url = "https://www.linkedin.com/in/somebody/"


class StubBrowser(object):
    """Enough of cc_linkedin_kit.browser.Browser for survey() to reach its first navigation
    and no further."""

    def __init__(self, seen):
        self.seen = seen
        self.page = StubPage()

    def goto(self, url, settle=4):
        # What the registry held at the moment the page was actually opened.
        self.seen.append([dict(v) for v in B.views_registered()])
        raise Navigated(url)


class ViewCase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cc-linkedin-views-")
        self._state = B.STATE_DIR
        B.STATE_DIR = self.dir
        self._gap = B.Pace.VIEW_GAP
        B.Pace.VIEW_GAP = (0, 0)
        del B._VIEWS[:]

    def tearDown(self):
        B.STATE_DIR = self._state
        B.Pace.VIEW_GAP = self._gap
        del B._VIEWS[:]
        shutil.rmtree(self.dir, ignore_errors=True)


class WhichCounterASurfaceIsOn(ViewCase):
    """`surface_kind` answers view_self ONLY for a surface positively identified
    as the owner's own. Everything else - including everything it does not
    recognise - is a capped view, because the unrecognised direction has to be
    the safe one."""

    def test_the_owners_own_profile_is_a_self_view(self):
        self.assertEqual(B.surface_kind("https://www.linkedin.com/in/sorenfrederiksen/"),
                         "view_self")

    def test_somebody_elses_profile_is_a_capped_view(self):
        self.assertEqual(B.surface_kind("https://www.linkedin.com/in/someone-else/"), "view")

    def test_the_owners_own_page_is_a_self_view_by_id_and_by_slug(self):
        for key in sorted(B.OWN_PAGE_KEYS):
            self.assertEqual(B.surface_kind("https://www.linkedin.com/company/%s/" % key),
                             "view_self", key)

    def test_the_owners_own_page_admin_screen_is_a_self_view(self):
        self.assertEqual(
            B.surface_kind("https://www.linkedin.com/company/centerconsulting-inc"
                           "/admin/analytics/updates/"), "view_self")

    def test_another_companys_page_is_a_capped_view(self):
        self.assertEqual(B.surface_kind("https://www.linkedin.com/company/some-other-firm/"),
                         "view")

    def test_our_own_notifications_are_a_self_view(self):
        self.assertEqual(B.surface_kind("https://www.linkedin.com/notifications/"), "view_self")

    def test_a_search_page_is_a_capped_view(self):
        self.assertEqual(
            B.surface_kind("https://www.linkedin.com/search/results/people/?keywords=x"), "view")

    def test_anything_unrecognised_is_capped_not_exempt(self):
        for url in ("https://www.linkedin.com/feed/",
                    "https://www.linkedin.com/mynetwork/",
                    "https://example.com/whatever",
                    "", None):
            self.assertEqual(B.surface_kind(url), "view", repr(url))

    def test_a_profile_named_like_the_owner_but_not_the_owner_is_capped(self):
        """The classifier reads the whole slug, not a substring of it:
        `sorenfrederiksen2` is somebody else."""
        self.assertEqual(B.surface_kind("https://www.linkedin.com/in/sorenfrederiksen2/"),
                         "view")


class TheSurveyToolRegistersItsView(ViewCase):
    """The half of F1 that changes what the counter sees."""

    def _survey(self, url):
        sv = _survey_tool()
        seen = []
        br = StubBrowser(seen)
        try:
            sv.survey(br, "a-label", url, sv.Dump(None, None), [], 4, 0, False)
        except Navigated:
            pass
        else:
            self.fail("the stub was never navigated - survey() did not reach its goto")
        return seen[0]

    def test_a_survey_of_somebody_elses_profile_is_counted_before_it_opens(self):
        at_navigation = self._survey("https://www.linkedin.com/in/someone-else/")
        self.assertEqual(len(at_navigation), 1,
                         "the view must be registered BEFORE the page is opened")
        self.assertEqual(at_navigation[0]["kind"], "view")
        self.assertTrue(at_navigation[0]["counted"],
                        "a survey under the cap must hold a counted slot")
        self.assertEqual(B.Pace().count("view"), 1)

    def test_a_survey_of_our_own_profile_is_counted_on_the_self_counter(self):
        at_navigation = self._survey("https://www.linkedin.com/in/sorenfrederiksen/")
        self.assertEqual([v["kind"] for v in at_navigation], ["view_self"])
        self.assertEqual(B.Pace().count("view_self"), 1)
        self.assertEqual(B.Pace().count("view"), 0)

    def test_a_survey_says_in_the_registry_what_it_opened(self):
        at_navigation = self._survey("https://www.linkedin.com/in/someone-else/")
        self.assertIn("survey", at_navigation[0]["what"].lower())

    def test_a_survey_over_the_cap_refuses_before_opening_anything(self):
        for _ in range(B.Pace.VIEW_CAP):
            p = B.Pace()
            p.before_view("a page")
            p.after_view()
        sv = _survey_tool()
        br = StubBrowser([])
        with self.assertRaises(SystemExit):
            sv.survey(br, "a-label", "https://www.linkedin.com/in/someone-else/",
                      sv.Dump(None, None), [], 4, 0, False)
        self.assertEqual(B.Pace().count("view"), B.Pace.VIEW_CAP,
                         "a refused survey must not take a slot")
        self.assertEqual(br.seen, [], "a refused survey must not open the page")


class TheCounterStatesItsRealScope(unittest.TestCase):
    """The half of F1 that changes what a reader believes.

    A PRESENCE check on all three surfaces, deliberately: an absence check here
    ("the docstring does not overclaim") would pass on a file that said nothing
    at all, which is the state this is fixing.
    """

    def _text(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_the_pace_docstring_states_the_scope_it_can_deliver(self):
        self.assertIn(SCOPE, B.Pace.__doc__ or "")

    def test_the_pace_docstring_names_the_path_it_cannot_see(self):
        self.assertIn(HAND, B.Pace.__doc__ or "")

    def test_the_readme_warns_that_a_hand_driven_view_is_invisible(self):
        self.assertIn(HAND, self._text(README))

    def test_the_skill_warns_that_a_hand_driven_view_is_invisible(self):
        self.assertIn(HAND, self._text(SKILL))


if __name__ == "__main__":
    unittest.main()
