"""Tests for plugins/tasks/hooks/park_on_end.py. Run: python3 -m unittest discover -s tests"""
import contextlib
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest

HOOKS = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "tasks" / "hooks"
sys.path.insert(0, str(HOOKS))
import park_on_end  # noqa: E402

NOTE = "---\nstatus: {status}\n---\n# t\n\n## Goal\ng\n\n## Log\n- [[2026-10-01]] 09:00 — started\n"
STAMP = "[[2026-10-29]] 16:40"
LINE = "- [[2026-10-29]] 16:40 — parked: session ended"


class ParkTest(unittest.TestCase):
    def test_active_note_is_parked_and_logged(self):
        out = park_on_end.park(NOTE.format(status="active"), STAMP)
        self.assertIn("\nstatus: parked\n", out)
        self.assertTrue(out.rstrip().endswith(LINE))

    def test_parked_and_done_notes_are_left(self):
        for s in ("parked", "done"):
            self.assertIsNone(park_on_end.park(NOTE.format(status=s), STAMP))

    def test_body_text_status_line_is_not_touched(self):
        text = NOTE.format(status="parked") + "status: active\n"
        self.assertIsNone(park_on_end.park(text, STAMP))

    def test_body_status_line_survives_when_frontmatter_is_active(self):
        out = park_on_end.park(NOTE.format(status="active") + "\nstatus: active\n", STAMP)
        self.assertIn("\nstatus: active\n", out.split("---\n", 2)[2])

    def test_log_line_goes_at_end_of_log_before_next_section(self):
        text = NOTE.format(status="active") + "\n## Later\nx\n"
        out = park_on_end.park(text, STAMP).splitlines()
        self.assertEqual(out[out.index("## Later") - 2], LINE)

    def test_missing_log_section_is_created_at_end(self):
        out = park_on_end.park("---\nstatus: active\n---\n# t\n", STAMP)
        self.assertTrue(out.endswith("## Log\n" + LINE + "\n"))


class MainTest(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)
        self.v1, self.v2 = self.home / "v1", self.home / "v2"
        for v in (self.v1, self.v2):
            (v / "Tasks" / ".session").mkdir(parents=True)
        cfg = self.home / "vaults.json"
        cfg.write_text(json.dumps({"default": "a", "timezone": "UTC",
                                   "vaults": {"a": {"path": str(self.v1)}, "b": {"path": str(self.v2)}}}))
        self.env = {"ADHD_PLANNER_VAULTS": str(cfg)}

    def run_main(self, sid="s1"):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = park_on_end.main(json.dumps({"session_id": sid}), self.env, str(self.home))
        return rc, err.getvalue()

    def test_main_parks_the_note_named_by_this_session(self):
        for v in (self.v1, self.v2):
            (v / "Tasks" / "t.md").write_text(NOTE.format(status="active"))
        (self.v2 / "Tasks" / ".session" / "s1").write_text("t\n")
        rc, err = self.run_main()
        self.assertEqual((rc, err), (0, ""))
        text = (self.v2 / "Tasks" / "t.md").read_text()
        self.assertIn("\nstatus: parked\n", text)
        self.assertIn("— parked: session ended", text)
        self.assertEqual((self.v1 / "Tasks" / "t.md").read_text(), NOTE.format(status="active"))

    def test_main_without_session_file_writes_nothing(self):
        p = self.v1 / "Tasks" / "t.md"
        p.write_text(NOTE.format(status="active"))
        os.utime(p, (1, 1))
        rc, err = self.run_main()
        self.assertEqual((rc, err, p.stat().st_mtime), (0, "", 1))

    def test_main_with_missing_note_names_the_path_and_returns_0(self):
        (self.v1 / "Tasks" / ".session" / "s1").write_text("gone\n")
        rc, err = self.run_main()
        self.assertEqual(rc, 0)
        self.assertIn(f"park_on_end: read note: {self.v1}/Tasks/gone.md", err)
        self.assertEqual(list((self.v1 / "Tasks").glob("*.md")), [])

    def test_bad_stdin_and_hostile_session_id_return_0(self):
        for stdin in ("", "not json", "[]", json.dumps({"session_id": "../x"})):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(park_on_end.main(stdin, self.env, str(self.home)), 0)


if __name__ == "__main__":
    unittest.main()
