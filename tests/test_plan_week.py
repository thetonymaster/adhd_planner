"""Tests for tools/plan_week.py's day picking. Run: python3 -m unittest tests.test_plan_week

Imports the plugin's plan_week.py directly; it reads the seed calendars.json beside it.
"""
import datetime as dt
import json
import pathlib
import subprocess
import sys
import tempfile
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


# A Mon-Fri week: 7h free a day (09:00-17:00 less lunch), 3h30 usable at --load 0.5;
# Tuesday has a 2h meeting (2h30 usable). The all-day event is ignored.
WEEK = ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"]
BUSY = {"events": [
    {"summary": "Planning", "start": {"dateTime": "2026-11-17T10:00:00-06:00"},
     "end": {"dateTime": "2026-11-17T12:00:00-06:00"}},
    {"summary": "Offsite", "start": {"date": "2026-11-18"}, "end": {"date": "2026-11-19"}},
]}
MIXED = [
    {"title": "a:write-report: Draft intro", "minutes": 120, "priority": "p2", "source": "vault"},
    {"title": "b:fix-bug: Reproduce", "minutes": 60, "deadline": "2026-11-17", "priority": "p1",
     "source": "vault"},
    {"title": "Call the dentist"},
    {"title": "c:old-thing: Finish it", "minutes": 200, "deadline": "2026-11-10", "priority": "p3",
     "source": "vault", "overdue": True},
    {"title": "Weekly review", "minutes": 30, "day": "wed", "priority": "p1"},
    {"title": "Huge task", "minutes": 300},
]


def run_cli(tasks, *flags):
    """Run plan_week.py on a fixed week; return (plan markdown, {week file: text}, stdout)."""
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        (d / "tasks.json").write_text(json.dumps(tasks), encoding="utf-8")
        (d / "busy.json").write_text(json.dumps(BUSY), encoding="utf-8")
        out = d / "out"
        r = subprocess.run(
            [sys.executable, str(TOOLS / "plan_week.py"), "--tasks", str(d / "tasks.json"),
             "--busy", str(d / "busy.json"), "--week-start", "2026-11-16", "--work", "09:00-17:00",
             "--lunch", "12:00-13:00", "--load", "0.5", "--out-dir", str(out), *flags],
            capture_output=True, text=True, check=True)
        md = (out / "weekly-plan-2026-11-16.md").read_text(encoding="utf-8")
        files = {p.name: p.read_text(encoding="utf-8") for p in sorted(out.glob("week-tasks-*.json"))}
        return md, files, r.stdout.replace(str(out), "<out>")


def plan_lines(md):
    return [ln for ln in md.splitlines() if ln.startswith("- [ ] ")]


class NoFlagPinnedTest(unittest.TestCase):
    """Without --keep-order the output is byte for byte what it was before the flag existed."""

    def test_output_without_the_flag_is_unchanged(self):
        md, files, stdout = run_cli(MIXED)
        self.assertEqual(md, (
            "# Week of Monday, November 16, 2026\n\n"
            "## Mon Nov 16\n_Free 7h · planning up to 3h30 · assigned 1h_\n"
            "- [ ] b:fix-bug: Reproduce — 60m (due 2026-11-17)\n\n"
            "## Tue Nov 17\n_Meetings (1): Planning_\n_Free 5h · planning up to 2h30 · assigned 0h_\n"
            "- (open — no tasks assigned)\n\n"
            "## Wed Nov 18\n_Free 7h · planning up to 3h30 · assigned 0h30_\n"
            "- [ ] Weekly review — 30m\n\n"
            "## Thu Nov 19\n_Free 7h · planning up to 3h30 · assigned 2h_\n"
            "- [ ] a:write-report: Draft intro — 120m\n\n"
            "## Fri Nov 20\n_Free 7h · planning up to 3h30 · assigned 0h25_\n"
            "- [ ] Call the dentist — 25m\n\n"
            "## Didn't fit this week\n"
            "- [ ] c:old-thing: Finish it — 200m (due 2026-11-10)\n"
            "- [ ] Huge task — 300m\n\n"
            "_Planned 3h55 of focus work across 5 days; 2 task(s) overflowed._\n"))
        self.assertEqual(files, {
            "week-tasks-2026-11-16.json": '[\n  {\n    "title": "b:fix-bug: Reproduce",\n    "minutes": 60\n  }\n]',
            "week-tasks-2026-11-18.json": '[\n  {\n    "title": "Weekly review",\n    "minutes": 30\n  }\n]',
            "week-tasks-2026-11-19.json": '[\n  {\n    "title": "a:write-report: Draft intro",\n    "minutes": 120\n  }\n]',
            "week-tasks-2026-11-20.json": '[\n  {\n    "title": "Call the dentist",\n    "minutes": 25\n  }\n]',
        })
        self.assertEqual(stdout, md + "\n---\nWrote <out>/weekly-plan-2026-11-16.md\n"
                         "Per-day task files for plan_day.py: week-tasks-2026-11-16.json, "
                         "week-tasks-2026-11-18.json, week-tasks-2026-11-19.json, week-tasks-2026-11-20.json\n"
                         "⚠ 2 task(s) didn't fit — decompose, extend the week, or defer.\n")


def keep(tasks, cap=None):
    cap = cap or {d: 210 for d in WEEK}
    return plan_week.distribute(tasks, WEEK, dict(cap), keep_order=True)


class KeepOrderTest(unittest.TestCase):
    """One test per row of the --keep-order table (design doc, Technical Plan section 5)."""

    def test_places_in_input_order(self):
        small = {"title": "small undated", "minutes": 25}
        big = {"title": "big due Wed", "minutes": 120, "deadline": "2026-11-18"}
        plan, overflow = keep([small, big])
        self.assertEqual((plan["2026-11-16"], overflow), ([small, big], []))

    def test_takes_the_earliest_eligible_day_with_room(self):
        task = {"title": "an hour", "minutes": 60}
        cap = {"2026-11-16": 30, "2026-11-17": 100, "2026-11-18": 210, "2026-11-19": 210, "2026-11-20": 210}
        plan, overflow = keep([task], cap)
        self.assertEqual((plan["2026-11-17"], overflow), ([task], []))

    def test_an_overdue_task_is_due_on_the_first_planned_day(self):
        task = {"title": "late", "minutes": 60, "deadline": "2026-11-10"}
        plan, overflow = keep([task])
        self.assertEqual((plan["2026-11-16"], overflow), ([task], []))

    def test_placement_continues_past_a_task_that_does_not_fit(self):
        huge = {"title": "huge", "minutes": 300}
        small = {"title": "small", "minutes": 25}
        plan, overflow = keep([huge, small])
        self.assertEqual((plan["2026-11-16"], overflow), ([small], [huge]))

    def test_a_row_with_no_minutes_counts_as_25(self):
        bare = {"title": "bare"}
        rest = {"title": "fills the rest", "minutes": 186}
        plan, overflow = keep([bare, rest])
        self.assertEqual((plan["2026-11-16"], plan["2026-11-17"], overflow), ([bare], [rest], []))


class KeepOrderOutputTest(unittest.TestCase):
    """The plan line under --keep-order: `- [ ] <title> — <minutes>m · <priority> (due <deadline>) (overdue)`."""

    def test_shows_the_priority_after_the_minutes(self):
        md, _, _ = run_cli([{"title": "ranked", "minutes": 60, "priority": "p1"}], "--keep-order")
        self.assertEqual(plan_lines(md), ["- [ ] ranked — 60m · p1"])

    def test_without_the_flag_the_priority_is_not_shown(self):
        md, _, _ = run_cli([{"title": "ranked", "minutes": 60, "priority": "p1"}])
        self.assertEqual(plan_lines(md), ["- [ ] ranked — 60m"])

    def test_an_overdue_row_is_placed_and_marked(self):
        md, _, _ = run_cli([{"title": "late", "minutes": 45, "deadline": "2026-11-10"}], "--keep-order")
        self.assertIn("## Mon Nov 16\n_Free 7h · planning up to 3h30 · assigned 0h45_\n"
                      "- [ ] late — 45m (due 2026-11-10) (overdue)\n", md)

    def test_an_overdue_row_that_does_not_fit_the_first_day_is_listed_with_the_mark(self):
        md, files, _ = run_cli([{"title": "late big", "minutes": 240, "deadline": "2026-11-10",
                                 "priority": "p0"}], "--keep-order")
        self.assertIn("## Didn't fit this week\n- [ ] late big — 240m · p0 (due 2026-11-10) (overdue)\n", md)
        self.assertEqual(files, {})

    def test_plan_line_form_with_and_without_each_part(self):
        tasks = [
            {"title": "all parts", "minutes": 45, "priority": "p2", "deadline": "2026-11-10"},
            {"title": "priority only", "minutes": 60, "priority": "p1"},
            {"title": "priority and due", "minutes": 30, "priority": "p3", "deadline": "2026-11-18"},
            {"title": "bare"},
            {"title": "due and overdue", "minutes": 20, "deadline": "2026-11-09"},
            {"title": "due only", "minutes": 300, "deadline": "2026-11-20"},
        ]
        md, _, _ = run_cli(tasks, "--keep-order")
        self.assertEqual(plan_lines(md), [
            "- [ ] all parts — 45m · p2 (due 2026-11-10) (overdue)",
            "- [ ] priority only — 60m · p1",
            "- [ ] priority and due — 30m · p3 (due 2026-11-18)",
            "- [ ] bare — 25m",
            "- [ ] due and overdue — 20m (due 2026-11-09) (overdue)",
            "- [ ] due only — 300m (due 2026-11-20)",
        ])

    def test_source_is_written_to_the_week_file_with_the_flag(self):
        tasks = [{"title": "v", "minutes": 30, "source": "vault"}, {"title": "inbox item", "minutes": 25}]
        _, files, _ = run_cli(tasks, "--keep-order")
        self.assertEqual(json.loads(files["week-tasks-2026-11-16.json"]),
                         [{"title": "v", "minutes": 30, "source": "vault"},
                          {"title": "inbox item", "minutes": 25}])

    def test_source_is_not_written_without_the_flag(self):
        _, files, _ = run_cli([{"title": "v", "minutes": 30, "source": "vault"}])
        self.assertEqual(json.loads(files["week-tasks-2026-11-16.json"]), [{"title": "v", "minutes": 30}])

    def test_a_pinned_row_keeps_its_day_under_the_flag(self):
        tasks = [{"title": "first", "minutes": 60, "priority": "p1"},
                 {"title": "on wed", "minutes": 30, "day": "wed", "priority": "p2"}]
        md, files, _ = run_cli(tasks, "--keep-order")
        self.assertIn("## Wed Nov 18\n_Free 7h · planning up to 3h30 · assigned 0h30_\n"
                      "- [ ] on wed — 30m · p2\n", md)
        self.assertEqual(sorted(files), ["week-tasks-2026-11-16.json", "week-tasks-2026-11-18.json"])


if __name__ == "__main__":
    unittest.main()
