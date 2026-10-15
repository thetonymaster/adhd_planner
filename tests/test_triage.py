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

SRC = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "planner" / "tools" / "triage.py"


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

    def test_the_summary_is_written_after_the_task_list(self):
        # morning-startup trusts tasks-<date>.json only when triage-<date>.md is at least as new.
        self.inbox.write_text("- a\n")
        self.apply([{"item": "a", "bucket": "today", "quadrant": "do"}])
        out = self.root / "tools" / "out"
        self.assertGreaterEqual((out / "triage-2026-10-13.md").stat().st_mtime_ns,
                                (out / "tasks-2026-10-13.json").stat().st_mtime_ns)

    def test_the_inbox_is_replaced_not_truncated_in_place(self):
        # A crash mid-write must not lose the kept lines: write a temp file, then os.replace.
        self.inbox.write_text("- a\nplain note\n")
        before = self.inbox.stat().st_ino
        self.apply([{"item": "a", "bucket": "today", "quadrant": "do"}])
        self.assertNotEqual(self.inbox.stat().st_ino, before)
        self.assertIn("plain note\n", self.inbox.read_text())
        self.assertEqual([p for p in self.root.glob("*.tmp") if not p.is_symlink()], [])

    def test_a_stale_tmp_link_is_not_written_through(self):
        self.inbox.write_text("- a\n")
        elsewhere = self.root / "elsewhere.md"
        elsewhere.write_text("untouched")
        (self.root / "inbox.md.tmp").symlink_to(elsewhere)
        self.apply([{"item": "a", "bucket": "today", "quadrant": "do"}])
        self.assertEqual(elsewhere.read_text(), "untouched")
        self.assertIn("# Capture inbox", self.inbox.read_text())

    def test_the_inbox_keeps_its_mode(self):
        self.inbox.write_text("- a\n")
        self.inbox.chmod(0o644)
        self.apply([{"item": "a", "bucket": "today", "quadrant": "do"}])
        self.assertEqual(self.inbox.stat().st_mode & 0o777, 0o644)

    def test_apply_clears_inbox_and_writes_tasks(self):
        self.inbox.write_text("- a\n- b\n")
        out = self.apply([
            {"item": "a", "bucket": "today", "quadrant": "do", "minutes": 30},
            {"item": "b", "bucket": "today", "quadrant": "delete"},
        ]).stdout
        self.assertEqual(json.loads(self.run_triage("parse").stdout.split("\n\n(")[0])["items"], [])
        self.assertIn("; inbox cleared", out)
        tasks = json.loads((self.root / "tools" / "out" / "tasks-2026-10-13.json").read_text())
        self.assertEqual(tasks, [{"title": "a", "minutes": 30}])

    def test_carry_appends_titles(self):
        self.inbox.write_text("- existing\n")
        items = self.root / "leftover.json"
        items.write_text(json.dumps([{"title": "undone"}, "also undone"]))
        self.run_triage("carry", "--items", str(items))
        self.assertEqual(self.inbox.read_text(), "- existing\n- undone\n- also undone\n")

    def test_apply_keeps_lines_that_are_not_bullets(self):
        self.inbox.write_text("# Capture inbox\n\n- a\n* starred thought\n1. numbered\nplain note\n  - nested\n")
        out = self.apply([
            {"item": "a", "bucket": "today", "quadrant": "do"},
            {"item": "nested", "bucket": "soon", "quadrant": "schedule"},
        ]).stdout
        inbox = self.inbox.read_text()
        for kept in ("* starred thought\n", "1. numbered\n", "plain note\n"):
            self.assertIn(kept, inbox)
        self.assertNotIn("\n- a\n", inbox)
        self.assertNotIn("nested", inbox)
        self.assertIn("Kept 3 line(s)", out)
        self.assertNotIn("inbox cleared", out)
        self.assertIn("items cleared from inbox", out)

    def test_apply_archives_bullets_verbatim(self):
        self.inbox.write_text("- a\n  - nested\n")
        self.apply([{"item": "a", "bucket": "today", "quadrant": "do"}])
        archived = self.archive.read_text()
        self.assertIn("\n- a\n", archived)
        self.assertIn("\n  - nested\n", archived)

    def test_the_template_is_never_archived_or_kept_twice(self):
        self.inbox.write_text("- a\n")
        self.apply([{"item": "a", "bucket": "today", "quadrant": "do"}])
        self.apply([])
        self.assertNotIn("Jot anything", self.archive.read_text())
        self.assertEqual(self.archive.read_text().count("- a"), 1)
        self.assertEqual(self.inbox.read_text().count("# Capture inbox"), 1)

    def test_the_seed_inbox_header_is_not_unparsed(self):
        seed = (SRC.parent / "inbox.md").read_text()
        self.inbox.write_text(seed + "- a\n")
        out = json.loads(self.run_triage("parse").stdout.split("\n\n(")[0])
        self.assertEqual((out["items"], out["unparsed"]), (["a"], []))

    def test_parse_reports_unparsed_lines(self):
        self.inbox.write_text("- a\nplain note\n")
        out = json.loads(self.run_triage("parse").stdout.split("\n\n(")[0])
        self.assertEqual(out["unparsed"], ["plain note"])


if __name__ == "__main__":
    unittest.main()
