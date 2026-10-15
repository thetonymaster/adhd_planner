"""Tests for tools/plan_day.py's scheduler. Run: python3 -m unittest tests.test_plan_day

Imports the plugin's plan_day.py directly; it reads the seed calendars.json beside it.
"""
import json
import pathlib
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "planner" / "tools"
sys.path.insert(0, str(TOOLS))
import plan_day  # noqa: E402

CFG = {"work": 25, "short": 5, "long": 30, "long_every": 4}
DAY = (9 * 60, 18 * 60)


def focus(blocks):
    return [(t, s, e) for k, t, s, e in blocks if k == "focus"]


def ev(summary, start, end):
    return {"summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end}}


class ShortTaskTest(unittest.TestCase):
    def test_a_task_under_five_minutes_is_placed_and_the_rest_follow(self):
        blocks, unscheduled = plan_day.schedule(
            [{"title": "tiny", "minutes": 3}, {"title": "big", "minutes": 50}], [], DAY, None, CFG)
        self.assertEqual(focus(blocks)[0], ("tiny", 540, 543))
        self.assertEqual(sum(e - s for _, s, e in focus(blocks)), 53)
        self.assertEqual(unscheduled, [])

    def test_a_zero_minute_task_is_skipped(self):
        blocks, unscheduled = plan_day.schedule(
            [{"title": "nothing", "minutes": 0}, {"title": "real", "minutes": 25}], [], DAY, None, CFG)
        self.assertEqual([t for t, _, _ in focus(blocks)], ["real"])
        self.assertEqual(unscheduled, [])

    def test_a_short_task_still_fits_a_small_gap(self):
        busy = [["a", 9 * 60 + 4, 18 * 60]]
        blocks, unscheduled = plan_day.schedule([{"title": "tiny", "minutes": 3}], busy, DAY, None, CFG)
        self.assertEqual(focus(blocks), [("tiny", 540, 543)])
        self.assertEqual(unscheduled, [])


class MidnightTest(unittest.TestCase):
    def busy(self, *events):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "busy.json"
            path.write_text(json.dumps({"events": list(events)}))
            return plan_day.load_busy(str(path), "2026-10-15")

    def test_a_meeting_into_the_next_day_blocks_until_midnight(self):
        self.assertEqual(self.busy(ev("late", "2026-10-15T17:00:00-06:00", "2026-10-16T01:00:00-06:00")),
                         [["late", 17 * 60, 24 * 60]])

    def test_a_meeting_from_the_previous_day_blocks_from_midnight(self):
        self.assertEqual(self.busy(ev("overnight", "2026-10-14T22:00:00-06:00", "2026-10-15T10:00:00-06:00")),
                         [["overnight", 0, 10 * 60]])

    def test_other_days_are_ignored(self):
        self.assertEqual(self.busy(ev("tomorrow", "2026-10-16T09:00:00-06:00", "2026-10-16T10:00:00-06:00"),
                                   ev("ends at midnight", "2026-10-14T23:00:00-06:00", "2026-10-15T00:00:00-06:00")),
                         [])

    def test_a_late_meeting_keeps_focus_out_of_the_evening(self):
        busy = self.busy(ev("late", "2026-10-15T17:00:00-06:00", "2026-10-16T01:00:00-06:00"))
        blocks, _ = plan_day.schedule([{"title": "x", "minutes": 600}], busy, DAY, None, CFG)
        self.assertLessEqual(max(e for _, _, e in focus(blocks)), 17 * 60)


if __name__ == "__main__":
    unittest.main()
