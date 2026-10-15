"""The PDF scripts without reportlab: an install hint and exit 2, not a traceback.
Run: python3 -m unittest tests.test_pdf_hint
"""
import pathlib
import subprocess
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "planner" / "tools"
# None in sys.modules makes `import reportlab…` raise ImportError, as if it weren't installed.
RUN = ("import runpy, sys; sys.modules['reportlab'] = None; sys.argv = sys.argv[1:]; "
       "runpy.run_path(sys.argv[0], run_name='__main__')")


class PdfHintTest(unittest.TestCase):
    def run_without_reportlab(self, script, *args):
        return subprocess.run([sys.executable, "-c", RUN, str(TOOLS / script), *args],
                              capture_output=True, text=True)

    def assertHint(self, out):
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertIn("uv venv .venv && uv pip install --python .venv reportlab", out.stderr)
        self.assertIn("python3 -m venv .venv && .venv/bin/pip install reportlab", out.stderr)
        self.assertNotIn("Traceback", out.stderr)
        self.assertNotIn("break-system-packages", out.stderr)

    def test_make_daily(self):
        self.assertHint(self.run_without_reportlab("make_daily.py", "--events", "none.json"))

    def test_make_insert(self):
        self.assertHint(self.run_without_reportlab("make_insert.py", "priority-matrix"))
