"""Tests for claude-config/hooks/load-task.sh. Run: python3 -m unittest discover -s tests"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import unittest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "claude-config" / "hooks" / "load-task.sh"
NOTE = "---\nstatus: {status}\n{repo}---\n# {slug}\n\n## Goal\ngoal {slug}\n\n## Next\n- [ ] step {slug}\n\n## Log\n"


class LoadTaskTest(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp())
        self.tasks = self.home / "vault" / "Tasks"
        self.tasks.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.home)

    def note(self, slug, status="active", repo="", mtime=None):
        path = self.tasks / f"{slug}.md"
        path.write_text(NOTE.format(slug=slug, status=status, repo=f"repo: {repo}\n" if repo else ""))
        if mtime is not None:
            os.utime(path, (mtime, mtime))

    def run_hook(self, payload=None, stdin=None):
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"]}
        data = json.dumps(payload).encode() if payload is not None else None
        out = subprocess.run(["bash", str(HOOK)], input=data, stdin=stdin, env=env,
                             capture_output=True, timeout=10, check=True)
        return out.stdout.decode()

    def test_override_beats_repo_and_global(self):
        self.note("bound", repo="~/code/app")
        self.note("mine")
        (self.tasks / ".active").write_text("bound\n")
        (self.tasks / ".session").mkdir()
        (self.tasks / ".session" / "s1").write_text("mine\n")
        out = self.run_hook({"session_id": "s1", "cwd": str(self.home / "code" / "app")})
        self.assertIn("Active task: mine (this session)", out)
        self.assertIn("step mine", out)

    def test_dangling_override_falls_through_to_repo(self):
        self.note("bound", repo="~/code/app/")
        (self.tasks / ".session").mkdir()
        (self.tasks / ".session" / "s1").write_text("gone\n")
        out = self.run_hook({"session_id": "s1", "cwd": str(self.home / "code" / "app" / "src")})
        self.assertIn("Active task: bound (project: app)", out)

    def test_deepest_then_active_then_newest_and_done_never_binds(self):
        self.note("outer", repo="~/r")
        self.note("inner", repo="~/r/sub")
        self.assertIn("Active task: inner", self.run_hook({"session_id": "x", "cwd": str(self.home / "r" / "sub")}))
        self.note("parked", status="parked", repo="~/p", mtime=time.time())
        self.note("active", status='"active"', repo='"~/p"', mtime=time.time() - 100)
        self.assertIn("Active task: active", self.run_hook({"session_id": "x", "cwd": str(self.home / "p")}))
        self.note("done", status="done", repo="~/d")
        (self.tasks / ".active").write_text("outer\n")
        self.assertIn("Active task: outer (global)", self.run_hook({"session_id": "x", "cwd": str(self.home / "d")}))

    def test_sibling_prefix_does_not_bind(self):
        self.note("sre", repo="~/work/infra")
        (self.tasks / ".active").write_text("sre\n")
        out = self.run_hook({"session_id": "x", "cwd": str(self.home / "work" / "infra-app")})
        self.assertIn("Active task: sre (global)", out)

    def test_no_stdin_or_bad_json_falls_back_without_hanging(self):
        self.note("g")
        (self.tasks / ".active").write_text("g\n")
        self.assertIn("Active task: g (global)", self.run_hook(stdin=subprocess.DEVNULL))
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"]}
        out = subprocess.run(["bash", str(HOOK)], input=b"not json", env=env, capture_output=True, timeout=10, check=True)
        self.assertIn("Active task: g (global)", out.stdout.decode())

    def test_an_unreadable_note_is_skipped_and_named(self):
        self.note("g")
        (self.tasks / ".active").write_text("g\n")
        (self.tasks / "bad.md").write_bytes(b"---\nrepo: \xff\n---\n")
        (self.tasks / "dir.md").mkdir()
        out = self.run_hook({"session_id": "x", "cwd": str(self.home)})
        self.assertIn("Active task: g (global)", out)
        self.assertIn("skipped unreadable notes: bad.md, dir.md", out)

    def test_a_failed_prune_is_named_and_does_not_block_the_task(self):
        self.assertNotEqual(os.geteuid(), 0, "run as non-root: root ignores the read-only .session dir")
        self.note("g")
        (self.tasks / ".active").write_text("g\n")
        sessions = self.tasks / ".session"
        sessions.mkdir()
        (sessions / "old").write_text("g\n")
        old = time.time() - 15 * 86400
        os.utime(sessions / "old", (old, old))
        sessions.chmod(0o500)
        try:
            out = self.run_hook({"session_id": "x", "cwd": str(self.home)})
        finally:
            sessions.chmod(0o700)
        self.assertIn("Active task: g (global)", out)
        self.assertIn("could not prune .session/old", out)

    def test_crlf_note_binds_to_its_repo(self):
        (self.tasks / "win.md").write_bytes(b"---\r\nstatus: active\r\nrepo: ~/code/app\r\n---\r\n# win\r\n")
        out = self.run_hook({"session_id": "x", "cwd": str(self.home / "code" / "app")})
        self.assertIn("Active task: win (project: app)", out)

    def test_prunes_overrides_older_than_14_days(self):
        self.note("g")
        (self.tasks / ".active").write_text("g\n")
        sessions = self.tasks / ".session"
        sessions.mkdir()
        (sessions / "old").write_text("g\n")
        (sessions / "new").write_text("g\n")
        old = time.time() - 15 * 86400
        os.utime(sessions / "old", (old, old))
        self.run_hook({"session_id": "x", "cwd": str(self.home)})
        self.assertFalse((sessions / "old").exists())
        self.assertTrue((sessions / "new").exists())


if __name__ == "__main__":
    unittest.main()
