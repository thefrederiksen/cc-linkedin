# -*- coding: utf-8 -*-
"""Design section 2: `connect` is capped per calendar day AND per rolling week,
and `pace.json` has to keep enough history for the second half to mean anything.

WHY THE ROLLING WINDOW IS A DIFFERENT KIND OF CHECK FROM THE DAILY ONE. The
daily cap is a property of one key in one file; the rolling cap is a property of
SEVEN keys, and the file used to delete every key that was not today's. So the
rolling sum over a file that has been saved once is always the same number as
the daily count, and a cap of 100 over seven days can never be reached however
many invitations go out - the check would pass forever without ever being wrong
out loud. That is the fail-open shape this repository has now met five times,
and it is why the retention change and the rolling check are ONE unit and land
together: a rolling check on a file that keeps one day is decoration.

WHAT THESE CANNOT PROVE, said plainly: nothing here proves LinkedIn's own limit
is 100 in seven days. That number is the published safe range's lower end, taken
from `docs/phase-3-design.md` section 2, and no run has ever been throttled to
measure it. What is proven is that the tool refuses at the number it was given,
that it counts the right days, and that the history it counts over survives.
"""
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit import browser as B


def day(offset):
    return (datetime.date.today() + datetime.timedelta(days=offset)).strftime("%Y-%m-%d")


class RollingCase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cc-linkedin-rolling-")
        self._state, B.STATE_DIR = B.STATE_DIR, self.dir
        self._gap, B.Pace.GAP = B.Pace.GAP, (0, 0)
        self._vgap, B.Pace.VIEW_GAP = B.Pace.VIEW_GAP, (0, 0)
        self.path = os.path.join(self.dir, "pace.json")

    def tearDown(self):
        B.STATE_DIR = self._state
        B.Pace.GAP = self._gap
        B.Pace.VIEW_GAP = self._vgap
        shutil.rmtree(self.dir, ignore_errors=True)

    def seed(self, counts):
        """counts: {day offset: connects that day}. Offsets are negative."""
        data = {str(day(o)): {"connect": n} for o, n in counts.items()}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def read(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)


class TheRollingWeekRefuses(RollingCase):

    def test_a_week_already_at_the_cap_refuses_before_acting(self):
        """P3-14. Six days holding the whole week's allowance between them, and
        today's daily count nowhere near its own cap of 20. The daily check
        passes and the rolling one must not."""
        self.seed({-6: 17, -5: 17, -4: 17, -3: 17, -2: 16, -1: 16})
        p = B.Pace()
        self.assertEqual(p.count("connect"), 0, "today has none of its own")
        with self.assertRaises(SystemExit) as e:
            p.before("connect")
        self.assertEqual(e.exception.code, 1)

    def test_the_same_week_one_short_of_the_cap_is_allowed(self):
        """The positive control. A refusal that fires whatever the numbers are
        is not a check, and this is the case that separates the two."""
        self.seed({-6: 17, -5: 17, -4: 17, -3: 17, -2: 16, -1: 15})
        B.Pace().before("connect")
        self.assertEqual(B.Pace().count("connect"), 1)

    def test_days_outside_the_window_do_not_count(self):
        """A day seven back is outside a seven-day window that includes today,
        and counting it would refuse a caller who is entitled to act."""
        self.seed({-7: 99, -8: 99})
        B.Pace().before("connect")
        self.assertEqual(B.Pace().count("connect"), 1)

    def test_the_window_is_the_sum_and_not_the_worst_day(self):
        """Seven quiet days that add up to the cap. A check that looked at the
        largest single day would pass every one of these."""
        self.seed({-6: 15, -5: 15, -4: 15, -3: 15, -2: 15, -1: 15})
        p = B.Pace()
        p.before("connect")           # 90 + 1 = 91
        for _ in range(9):
            p.before("connect")       # up to 100
        self.assertEqual(p.count("connect"), 10)
        with self.assertRaises(SystemExit):
            p.before("connect")

    def test_the_daily_cap_still_bites_inside_a_quiet_week(self):
        """The two caps are AND, not OR. An empty week and twenty today must
        still refuse the twenty-first."""
        self.seed({})
        p = B.Pace()
        for _ in range(B.Pace.CAPS["connect"]):
            p.before("connect")
        with self.assertRaises(SystemExit) as e:
            p.before("connect")
        self.assertEqual(e.exception.code, 1)

    def test_a_refused_connect_takes_no_slot(self):
        """A cap that consumed a slot on the way to refusing would make the
        NEXT day's budget smaller for having been refused."""
        self.seed({-6: 17, -5: 17, -4: 17, -3: 17, -2: 16, -1: 16})
        p = B.Pace()
        with self.assertRaises(SystemExit):
            p.before("connect")
        self.assertEqual(p.count("connect"), 0)


class TheHistoryTheWindowNeeds(RollingCase):

    def test_a_save_keeps_at_least_eight_days(self):
        """pace.json used to delete every day key older than today, which makes
        the rolling sum identical to the daily count forever."""
        self.seed({-7: 1, -6: 1, -5: 1, -4: 1, -3: 1, -2: 1, -1: 1})
        B.Pace().before("connect")
        kept = [k for k in self.read() if B.DAY_KEY.match(k)]
        self.assertGreaterEqual(len(kept), 8,
                                "the rolling window needs the history it counts over: %s" % kept)
        for o in range(-7, 1):
            self.assertIn(day(o), kept, "day %d was dropped" % o)

    def test_a_day_far_outside_the_window_is_still_pruned(self):
        """Retention is a window, not an accumulation. A file that grows forever
        is a different defect from one that keeps nothing."""
        self.seed({-40: 5, -1: 1})
        B.Pace().before("connect")
        kept = [k for k in self.read() if B.DAY_KEY.match(k)]
        self.assertNotIn(day(-40), kept)
        self.assertIn(day(-1), kept)

    def test_the_retention_covers_the_window_it_is_for(self):
        """The two numbers are coupled and neither is free to move alone."""
        self.assertGreaterEqual(B.Pace.RETAIN_DAYS, B.Pace.ROLLING_CAPS["connect"][1] + 1,
                                "retaining %d days cannot serve a %d-day window"
                                % (B.Pace.RETAIN_DAYS, B.Pace.ROLLING_CAPS["connect"][1]))


class WhatTheRollingCheckCounts(RollingCase):

    def test_only_the_kind_asked_about(self):
        """A week of withdrawals must not spend the invitation budget."""
        data = {day(-1): {"withdraw": 99, "view": 500}}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        B.Pace().before("connect")
        self.assertEqual(B.Pace().count("connect"), 1)

    def test_a_kind_with_no_rolling_cap_is_not_given_one(self):
        """message is 30 a day and nothing else. A rolling cap applied to every
        outbound kind by accident would refuse a caller silently."""
        self.assertNotIn("message", B.Pace.ROLLING_CAPS)
        self.seed({})
        data = {day(-o): {"message": 29} for o in range(1, 7)}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        B.Pace().before("message")
        self.assertEqual(B.Pace().count("message"), 1)


if __name__ == "__main__":
    unittest.main()
