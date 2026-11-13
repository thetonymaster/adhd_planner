"""Tests for tools/setup_check.py. Run: python3 -m unittest tests.test_setup_check"""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "planner" / "tools"


class RequiredScriptsTest(unittest.TestCase):
    def test_missing_task_queue_is_reported(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        tools = tmp / "tools"
        shutil.copytree(TOOLS, tools, ignore=shutil.ignore_patterns("__pycache__", "out"))
        (tools / "task_queue.py").unlink()
        r = subprocess.run([sys.executable, str(tools / "setup_check.py")],
                           capture_output=True, text=True, cwd=tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        missing = [l for l in r.stdout.splitlines() if "tool scripts missing" in l]
        self.assertEqual(len(missing), 1, r.stdout)
        self.assertIn("task_queue.py", missing[0])


if __name__ == "__main__":
    unittest.main()
