# -*- coding: utf-8 -*-
"""R20: the selftest fixtures live outside the repository, not nowhere.

RULING R20, the Architect's, 2026-09-10.

The rule that no third party's URL or details may be committed is right and it
stands - this repository is PUBLIC. But it was only half a rule: it said where
the fixture values may NOT go and left them nowhere else, so the two profiles
the Phase 2 rows need were rediscovered by hand by each new seat, out of the
daily view cap, and thrown away again. The measurement was made three times and
kept none of the times.

So: the REPOSITORY documents the SHAPE a fixture must have, and the MACHINE
holds the values, in the state directory beside pace.json - which is not in git
and never will be. The flags still exist and still win when passed.

WHAT MUST NOT HAPPEN, and it is what these tests are mostly about: a fixture
file that is missing, unreadable or half-filled must FAIL THE RUN, naming what
is absent. It must never let the run continue with a row quietly skipped. That
is the oldest defect in this suite - a missing fixture producing not a failed
row but NO ROW AT ALL - and moving the values to a file is exactly the change
that could reintroduce it.

No browser, no network.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit import browser as B
from kit import fixtures as F


class FixtureCase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cc-linkedin-fixtures-")
        self._state = B.STATE_DIR
        # What the MACHINE'S real fixtures file looks like right now, so tearDown
        # can prove this test did not touch it. Not hypothetical: the first run
        # of this suite wrote three fabricated fixtures into the real state
        # directory, because kit/fixtures.py bound STATE_DIR at import time and
        # the redirection below could not reach it. A test that can write to the
        # machine's own state is a test that will, eventually, delete something.
        self._real = os.path.join(self._state, "selftest-fixtures.json")
        self._real_before = self._snapshot(self._real)
        B.STATE_DIR = self.dir
        self.path = os.path.join(self.dir, "selftest-fixtures.json")

    def tearDown(self):
        B.STATE_DIR = self._state
        shutil.rmtree(self.dir, ignore_errors=True)
        self.assertEqual(self._snapshot(self._real), self._real_before,
                         "this test wrote to the MACHINE'S real fixtures file at %s"
                         % self._real)

    @staticmethod
    def _snapshot(path):
        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError:
            return None

    def write(self, data):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def a_good_one(self):
        return {
            "other_profile": {"url": "https://www.linkedin.com/in/someone/",
                              "expect": "name=A B; headline=x; location=y; company=z; "
                                        "degree=2nd; primary=Connect; can_connect=yes; "
                                        "connections=500+"},
            "menu_profile": {"url": "https://www.linkedin.com/in/another/",
                             "expect": "name=C D; headline=x; location=y; company=none; "
                                       "degree=2nd; primary=Message; can_connect=yes; "
                                       "connections=500+"},
        }


class TheValuesComeFromTheMachineNotTheRepository(FixtureCase):

    def test_the_file_lives_beside_pace_json_and_not_in_the_tree(self):
        self.assertEqual(os.path.dirname(F.path()), B.STATE_DIR)
        self.assertEqual(os.path.basename(F.path()), "selftest-fixtures.json")
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertFalse(os.path.abspath(F.path()).startswith(os.path.abspath(repo) + os.sep),
                         "the fixtures file resolves to a path inside the repository")

    def test_a_value_is_read_from_the_file_when_the_flag_is_absent(self):
        self.write(self.a_good_one())
        self.assertEqual(F.value(None, "other_profile", "url"),
                         "https://www.linkedin.com/in/someone/")

    def test_the_flag_wins_over_the_file(self):
        self.write(self.a_good_one())
        self.assertEqual(F.value("https://www.linkedin.com/in/passed-in/", "other_profile", "url"),
                         "https://www.linkedin.com/in/passed-in/")

    def test_no_file_at_all_yields_nothing_rather_than_raising(self):
        """Absence is answered by the CALLER, which fails the run naming both the
        flag and the file. This function's job is only to say it has nothing."""
        self.assertIsNone(F.value(None, "other_profile", "url"))


class AMissingFixtureFAILSTheRun(FixtureCase):
    """The whole risk of R20. A file makes it easy to end up half-configured,
    and the failure this suite must never have is a row that does not run."""

    def test_an_absent_file_is_a_failure_naming_what_is_missing(self):
        with self.assertRaises(SystemExit):
            F.require(None, "other_profile", "url", "--other-profile")

    def test_a_file_missing_ONE_key_still_fails(self):
        data = self.a_good_one()
        del data["menu_profile"]["expect"]
        self.write(data)
        F.require(None, "menu_profile", "url", "--menu-profile")      # this one is there
        with self.assertRaises(SystemExit):
            F.require(None, "menu_profile", "expect", "--menu-expect")

    def test_an_empty_value_is_treated_as_missing(self):
        """An empty string is the shape R8 already ruled on: `headline=` used to
        be accepted and asserted nothing. An empty fixture value is the same
        defect one layer out."""
        data = self.a_good_one()
        data["other_profile"]["url"] = "   "
        self.write(data)
        with self.assertRaises(SystemExit):
            F.require(None, "other_profile", "url", "--other-profile")

    def test_a_file_that_does_not_parse_is_a_LOUD_failure_not_an_empty_one(self):
        """A corrupt fixtures file must not read as 'no fixtures configured' and
        certainly not as 'nothing to check'. It is a broken instrument."""
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{ this is not json")
        with self.assertRaises(SystemExit):
            F.value(None, "other_profile", "url")

    def test_a_file_that_is_not_an_object_is_a_LOUD_failure(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write('["a list"]')
        with self.assertRaises(SystemExit):
            F.value(None, "other_profile", "url")

    def test_the_failure_names_the_flag_and_the_file(self):
        try:
            F.require(None, "menu_profile", "url", "--menu-profile")
        except SystemExit:
            pass
        # the message is what a person acts on; assert it carries both routes in
        self.assertIn("--menu-profile", F.last_message)
        self.assertIn("selftest-fixtures.json", F.last_message)


class WritingOneBack(FixtureCase):
    """Discovering a fixture costs views out of the safety cap, so a seat that
    discovers one records it. R20's 'this is the last time anyone pays'."""

    def test_a_recorded_fixture_can_be_read_back(self):
        F.record("menu_profile", url="https://www.linkedin.com/in/x/", expect="company=none",
                 measured="2026-09-10: no company pill, invite behind More")
        self.assertEqual(F.value(None, "menu_profile", "url"), "https://www.linkedin.com/in/x/")
        self.assertIn("no company pill", F.value(None, "menu_profile", "measured"))

    def test_recording_one_does_not_lose_another(self):
        self.write(self.a_good_one())
        F.record("pending_profile", url="https://www.linkedin.com/in/y/", expect="can_connect=no",
                 measured="2026-09-10: invitation already sent")
        self.assertEqual(F.value(None, "other_profile", "url"),
                         "https://www.linkedin.com/in/someone/")
        self.assertEqual(F.value(None, "pending_profile", "url"),
                         "https://www.linkedin.com/in/y/")

    def test_the_file_it_writes_is_the_one_it_reads(self):
        F.record("other_profile", url="https://www.linkedin.com/in/z/", expect="a=b")
        self.assertTrue(os.path.exists(self.path))
        with open(self.path, encoding="utf-8") as f:
            self.assertIn("other_profile", json.load(f))


if __name__ == "__main__":
    unittest.main()
