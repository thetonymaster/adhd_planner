"""Tests for tools/habits.py. Run: python3 -m unittest tests.test_habits

Each test copies the plugin's habits.py into a temp planner folder, because the
script reads habits.json and writes habits-log.json next to its tools/ directory.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "planner" / "tools" / "habits.py"
HABITS = {"habits": [
    {"id": "sleep-bedtime", "label": "In bed by bedtime", "area": "sleep"},
    {"id": "eat-morning", "label": "Breakfast", "area": "eating"},
    {"id": "walk", "label": "Walk", "area": "commitment"},
]}


class HabitsLogTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        (self.root / "tools").mkdir()
        shutil.copy(SRC, self.root / "tools" / "habits.py")
        (self.root / "habits.json").write_text(json.dumps(HABITS), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.root)

    def log(self, done, date="2026-10-14"):
        subprocess.run([sys.executable, "tools/habits.py", "log", "--done", done, "--date", date],
                       cwd=self.root, capture_output=True, text=True, check=True)
        return json.loads((self.root / "habits-log.json").read_text(encoding="utf-8"))

    def test_a_second_log_the_same_day_adds_to_it(self):
        self.log("sleep-bedtime")
        day = self.log("eat-morning")["2026-10-14"]
        self.assertEqual(day, {"sleep-bedtime": True, "eat-morning": True, "walk": False})

    def test_an_empty_log_keeps_what_was_done(self):
        self.log("sleep-bedtime,walk")
        day = self.log("")["2026-10-14"]
        self.assertEqual(day, {"sleep-bedtime": True, "eat-morning": False, "walk": True})

    def test_other_days_are_untouched(self):
        self.log("walk", date="2026-10-13")
        log = self.log("sleep-bedtime")
        self.assertEqual(log["2026-10-13"], {"sleep-bedtime": False, "eat-morning": False, "walk": True})


if __name__ == "__main__":
    unittest.main()
