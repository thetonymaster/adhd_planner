"""Tests for tools/planner_config.py and the scripts that read it.
Run: python3 -m unittest tests.test_planner_config

Script tests copy the tools into a temp planner folder, because plan_day.py and
plan_week.py read calendars.json and write out/ next to themselves.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "planner" / "tools"
sys.path.insert(0, str(TOOLS))
import planner_config  # noqa: E402


class LoadTest(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.path = self.dir / "calendars.json"

    def tearDown(self):
        shutil.rmtree(self.dir)

    def load(self, data):
        self.path.write_text(json.dumps(data))
        return planner_config.load(str(self.path))

    def test_missing_keys_keep_todays_defaults(self):
        cfg = self.load({"timezone": "Europe/Madrid"})
        self.assertEqual(cfg["timezone"], "Europe/Madrid")
        self.assertEqual(cfg["work"], (9 * 60, 18 * 60))
        self.assertEqual(cfg["lunch"], (14 * 60, 15 * 60))
        self.assertEqual(cfg["pomodoro"], {"work": 25, "break": 5, "long": 30, "long_every": 4})

    def test_values_from_the_file(self):
        cfg = self.load({"work": "08:30-16:30", "lunch": "12:00-12:45", "pomodoro": {"work": 50, "break": 10}})
        self.assertEqual(cfg["work"], (510, 990))
        self.assertEqual(cfg["lunch"], (720, 765))
        self.assertEqual(cfg["pomodoro"], {"work": 50, "break": 10, "long": 30, "long_every": 4})

    def test_lunch_null_means_no_lunch(self):
        self.assertIsNone(self.load({"lunch": None})["lunch"])
        self.assertIsNone(self.load({"lunch": ""})["lunch"])

    def test_bad_work_value_names_the_key(self):
        with self.assertRaises(planner_config.ConfigError) as e:
            self.load({"work": "9-5"})
        self.assertIn('"work"', str(e.exception))
        self.assertIn("'9-5'", str(e.exception))
        self.assertIn("calendars.json", str(e.exception))

    def test_end_before_start_is_an_error(self):
        with self.assertRaises(planner_config.ConfigError):
            self.load({"lunch": "15:00-14:00"})

    def test_bad_pomodoro_value_names_the_key(self):
        with self.assertRaises(planner_config.ConfigError) as e:
            self.load({"pomodoro": {"work": 0}})
        self.assertIn('"pomodoro.work"', str(e.exception))

    def test_non_string_timezone_names_the_key_and_value(self):
        with self.assertRaises(planner_config.ConfigError) as e:
            self.load({"timezone": 5})
        self.assertIn("timezone", str(e.exception))
        self.assertIn("5", str(e.exception))

    def test_long_every_error_says_a_count_not_minutes(self):
        with self.assertRaises(planner_config.ConfigError) as e:
            self.load({"pomodoro": {"long_every": 0}})
        self.assertIn("a whole number ≥ 1", str(e.exception))
        self.assertNotIn("minutes", str(e.exception))

    def test_missing_file_warns_and_uses_defaults(self):
        cfg = planner_config.load(str(self.dir / "absent.json"))
        self.assertEqual(cfg["work"], (540, 1080))
        self.assertEqual(cfg["timezone"], "UTC")

    def test_invalid_json_is_an_error_not_the_defaults(self):
        self.path.write_text("{not json")
        with self.assertRaises(planner_config.ConfigError) as e:
            planner_config.load(str(self.path))
        self.assertIn("not valid JSON", str(e.exception))

    def test_empty_or_null_timezone_is_an_error(self):
        for tz in (None, "", False):
            with self.assertRaises(planner_config.ConfigError, msg=repr(tz)):
                self.load({"timezone": tz})

    def test_unknown_timezone_is_an_error(self):
        with self.assertRaises(planner_config.ConfigError) as e:
            self.load({"timezone": "Mars/Olympus"})
        self.assertIn("Mars/Olympus", str(e.exception))
        self.assertEqual(self.load({"timezone": "Europe/Madrid"})["timezone"], "Europe/Madrid")

    def test_unreadable_file_is_an_error_not_the_defaults(self):
        self.path.mkdir()  # a directory where the file should be: open() raises IsADirectoryError
        with self.assertRaises(planner_config.ConfigError) as e:
            planner_config.load(str(self.path))
        self.assertIn("could not read", str(e.exception))

    def test_lunch_false_or_zero_is_an_error(self):
        for lunch in (False, 0):
            with self.assertRaises(planner_config.ConfigError, msg=repr(lunch)):
                self.load({"lunch": lunch})


class ScriptTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.tools = self.root / "tools"
        self.tools.mkdir()
        for name in ("plan_day.py", "plan_week.py", "planner_config.py", "setup_check.py"):
            shutil.copy(TOOLS / name, self.tools / name)
        (self.root / "tasks.json").write_text(json.dumps([{"title": "Write", "minutes": 50}]))

    def tearDown(self):
        shutil.rmtree(self.root)

    def calendars(self, data):
        (self.tools / "calendars.json").write_text(json.dumps(data))

    def run_tool(self, *args, check=True):
        return subprocess.run([sys.executable, *args], cwd=self.root, capture_output=True, text=True, check=check)

    def first_focus(self, date="2026-10-15"):
        blocks = json.loads((self.tools / "out" / f"schedule-{date}.json").read_text())
        return next(b for b in blocks if b["kind"] == "focus")

    def test_plan_day_reads_work_and_pomodoro(self):
        self.calendars({"timezone": "UTC", "work": "10:00-12:00", "lunch": None, "pomodoro": {"work": 50}})
        self.run_tool("tools/plan_day.py", "--tasks", "tasks.json", "--date", "2026-10-15")
        self.assertEqual(self.first_focus(), {"kind": "focus", "title": "Write", "start": "10:00", "end": "10:50"})

    def test_flags_override_the_file(self):
        self.calendars({"work": "10:00-12:00", "pomodoro": {"work": 50}})
        self.run_tool("tools/plan_day.py", "--tasks", "tasks.json", "--date", "2026-10-15",
                      "--work", "08:00-12:00", "--work-min", "25")
        self.assertEqual(self.first_focus()["start"], "08:00")
        self.assertEqual(self.first_focus()["end"], "08:25")

    def test_empty_lunch_flag_overrides_file(self):
        self.calendars({"work": "14:00-16:00", "lunch": "14:00-15:00"})
        self.run_tool("tools/plan_day.py", "--tasks", "tasks.json", "--date", "2026-10-15")
        self.assertEqual(self.first_focus()["start"], "15:00")
        self.run_tool("tools/plan_day.py", "--tasks", "tasks.json", "--date", "2026-10-15", "--lunch", "")
        self.assertEqual(self.first_focus()["start"], "14:00")

    def test_plan_day_bad_config_exits_2_without_traceback(self):
        self.calendars({"work": "9-5"})
        out = self.run_tool("tools/plan_day.py", "--tasks", "tasks.json", check=False)
        self.assertEqual(out.returncode, 2)
        self.assertIn('"work"', out.stderr)
        self.assertNotIn("Traceback", out.stderr)

    def test_plan_week_reads_work_and_lunch(self):
        self.calendars({"work": "09:00-12:00", "lunch": "11:00-12:00"})
        out = self.run_tool("tools/plan_week.py", "--tasks", "tasks.json", "--week-start", "2026-10-12", "--load", "1")
        self.assertIn("_Free 2h · planning up to 2h", out.stdout)

    def test_plan_week_writes_week_tasks_files(self):
        self.run_tool("tools/plan_week.py", "--tasks", "tasks.json", "--week-start", "2026-10-12", "--load", "1")
        names = sorted(p.name for p in (self.tools / "out").glob("*.json"))
        self.assertEqual(names, ["week-tasks-2026-10-12.json"])

    def test_plan_week_rerun_removes_stale_day_files(self):
        out = self.tools / "out"
        out.mkdir()
        (out / "week-tasks-2026-10-13.json").write_text("[]")
        self.run_tool("tools/plan_week.py", "--tasks", "tasks.json", "--week-start", "2026-10-12", "--load", "1")
        self.assertFalse((out / "week-tasks-2026-10-13.json").exists())
        self.assertTrue((out / "week-tasks-2026-10-12.json").exists())

    def test_setup_check_reports_the_day(self):
        self.calendars({"timezone": "Europe/Madrid", "work": "10:00-12:00", "lunch": None})
        out = self.run_tool("tools/setup_check.py", check=False)
        self.assertIn("work 10:00-12:00, lunch none, Pomodoro 25/5", out.stdout)
        self.calendars({"work": "9-5"})
        out = self.run_tool("tools/setup_check.py", check=False)
        self.assertIn("calendars.json day settings invalid", out.stdout)

    def test_setup_check_without_planner_config_fails_cleanly(self):
        (self.tools / "planner_config.py").unlink()
        self.calendars({"timezone": "UTC"})
        out = self.run_tool("tools/setup_check.py", check=False)
        self.assertIn("planner_config.py", out.stdout)
        self.assertNotIn("Traceback", out.stderr)
