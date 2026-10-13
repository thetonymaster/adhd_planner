"""Tests for tools/triage.py. Run: python3 -m unittest discover -s tests

Each test copies the plugin's triage.py into a temp planner folder, because the
script writes inbox-archive.md next to its own tools/ directory.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = pathlib.Path(__file__).resolve().parent.parent / "planner-plugin" / "tools" / "triage.py"


class TriageTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        (self.root / "tools").mkdir()
        shutil.copy(SRC, self.root / "tools" / "triage.py")
        self.inbox = self.root / "inbox.md"
        self.archive = self.root / "inbox-archive.md"

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_triage(self, *args):
        return subprocess.run(
            [sys.executable, "tools/triage.py", *args],
            cwd=self.root, capture_output=True, text=True, check=True)

    def apply(self, decisions):
        path = self.root / "decisions.json"
        path.write_text(json.dumps(decisions))
        return self.run_triage("apply", "--decisions", str(path), "--date", "2026-10-13")

    def test_parse_skips_empty_placeholder(self):
        self.inbox.write_text("# Capture inbox\n\n- buy milk\n- \n- call bank\n")
        out = json.loads(self.run_triage("parse").stdout.split("\n\n(")[0])
        self.assertEqual(out["items"], ["buy milk", "call bank"])

    def test_apply_archives_vault_bullets_appended_to_inbox(self):
        # capture-triage appends the vault inbox bullets to inbox.md before
        # parse; apply must archive them before the skill deletes them from
        # the vault.
        self.inbox.write_text("- planner item\n")
        with self.inbox.open("a") as f:
            f.write("- vault item\n")
        self.apply([
            {"item": "planner item", "bucket": "today", "quadrant": "do", "minutes": 25},
            {"item": "vault item", "bucket": "soon", "quadrant": "schedule", "minutes": 50},
        ])
        archived = self.archive.read_text()
        self.assertIn("- planner item", archived)
        self.assertIn("- vault item", archived)

    def test_apply_archives_items_missing_from_decisions(self):
        # Nothing in the inbox is lost even if classification skipped it.
        self.inbox.write_text("- classified\n- forgotten\n")
        self.apply([{"item": "classified", "bucket": "today", "quadrant": "do"}])
        self.assertIn("- forgotten", self.archive.read_text())

    def test_apply_clears_inbox_and_writes_tasks(self):
        self.inbox.write_text("- a\n- b\n")
        self.apply([
            {"item": "a", "bucket": "today", "quadrant": "do", "minutes": 30},
            {"item": "b", "bucket": "today", "quadrant": "delete"},
        ])
        self.assertEqual(json.loads(self.run_triage("parse").stdout.split("\n\n(")[0])["items"], [])
        tasks = json.loads((self.root / "tools" / "out" / "tasks-2026-10-13.json").read_text())
        self.assertEqual(tasks, [{"title": "a", "minutes": 30}])

    def test_carry_appends_titles(self):
        self.inbox.write_text("- existing\n")
        items = self.root / "leftover.json"
        items.write_text(json.dumps([{"title": "undone"}, "also undone"]))
        self.run_triage("carry", "--items", str(items))
        self.assertEqual(self.inbox.read_text(), "- existing\n- undone\n- also undone\n")


if __name__ == "__main__":
    unittest.main()
