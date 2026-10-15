"""Tests for tools/plan_week.py's day picking. Run: python3 -m unittest tests.test_plan_week

Imports the plugin's plan_week.py directly; it reads the seed calendars.json beside it.
"""
import datetime as dt
import pathlib
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "planner" / "tools"
sys.path.insert(0, str(TOOLS))
import plan_week  # noqa: E402

D = dt.date.fromisoformat


class PlanDaysTest(unittest.TestCase):
    def test_default_starts_today_in_this_week(self):
        self.assertEqual(plan_week.plan_days(D("2026-10-15"), None, False),
                         (D("2026-10-12"), ["2026-10-15", "2026-10-16"]))

    def test_monday_plans_the_whole_week(self):
        self.assertEqual(plan_week.plan_days(D("2026-10-12"), None, False)[1],
                         ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"])

    def test_the_weekend_plans_next_week(self):
        for today in ("2026-10-17", "2026-10-18"):
            with self.subTest(today):
                self.assertEqual(plan_week.plan_days(D(today), None, False),
                                 (D("2026-10-19"), ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"]))

    def test_include_weekend_runs_to_sunday(self):
        self.assertEqual(plan_week.plan_days(D("2026-10-16"), None, True)[1],
                         ["2026-10-16", "2026-10-17", "2026-10-18"])

    def test_an_explicit_week_start_plans_every_day(self):
        self.assertEqual(plan_week.plan_days(D("2026-10-15"), D("2026-10-12"), False),
                         (D("2026-10-12"), ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"]))

    def test_a_task_pinned_to_a_past_day_overflows(self):
        task = {"title": "standup notes", "minutes": 25, "day": "mon"}
        days = ["2026-10-15", "2026-10-16"]
        plan, overflow = plan_week.distribute([task], days, {d: 300 for d in days})
        self.assertEqual((plan, overflow), ({d: [] for d in days}, [task]))


if __name__ == "__main__":
    unittest.main()
