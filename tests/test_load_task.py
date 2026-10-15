"""Tests for plugins/tasks/hooks/load-task.sh. Run: python3 -m unittest discover -s tests"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import unittest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "tasks" / "hooks" / "load-task.sh"
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

    def run_hook(self, payload=None, stdin=None, env_extra=None):
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"], **(env_extra or {})}
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

    def test_an_unreadable_active_note_keeps_the_vault_and_task_lines(self):
        (self.tasks / "g.md").write_bytes(b"\xff\xfe")
        (self.tasks / ".active").write_text("g\n")
        out = self.run_hook({"session_id": "x", "cwd": str(self.home)})
        self.assertIn(f"Vault: {self.home / 'vault'}\n", out)
        self.assertIn("Active task: g (global)", out)
        self.assertIn(f"(could not read {self.tasks / 'g.md'}: UnicodeDecodeError", out)

    def test_a_resolver_error_falls_back_to_the_default_vaults_active_task(self):
        self.assertNotEqual(os.geteuid(), 0, "run as non-root: root reads mode 000 files")
        self.note("g")
        (self.tasks / ".active").write_text("g\n")
        sessions = self.tasks / ".session"
        sessions.mkdir()
        override = sessions / "x"
        override.write_text("g\n")
        override.chmod(0)
        try:
            out = self.run_hook({"session_id": "x", "cwd": str(self.home)})
        finally:
            override.chmod(0o600)
        self.assertIn("Active task: g (global (resolver error: PermissionError", out)

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

    def test_repo_reached_through_a_symlink_binds(self):
        real = self.home / "real" / "app"
        real.mkdir(parents=True)
        os.symlink(self.home / "real", self.home / "link")
        self.note("viasym", repo="~/link/app")
        out = self.run_hook({"session_id": "x", "cwd": str(real)})
        self.assertIn("Active task: viasym (project: app)", out)
        self.note("viareal", repo="~/real/app", mtime=time.time() + 10)
        os.remove(self.tasks / "viasym.md")
        out = self.run_hook({"session_id": "x", "cwd": str(self.home / "link" / "app")})
        self.assertIn("Active task: viareal (project: app)", out)

    def test_plugin_option_beats_vault_env(self):
        other = self.home / "elsewhere" / "Tasks"
        other.mkdir(parents=True)
        (other / "opt.md").write_text(NOTE.format(slug="opt", status="active", repo=""))
        (other / ".active").write_text("opt\n")
        (self.tasks / ".active").write_text("ignored\n")
        out = self.run_hook({"session_id": "x", "cwd": "/"}, env_extra={
            "CLAUDE_PLUGIN_OPTION_VAULTPATH": str(self.home / "elsewhere"),
            "VAULT": str(self.home / "vault")})
        self.assertIn("Active task: opt (global)", out)

    def test_tilde_in_option_is_expanded(self):
        alt = self.home / "alt" / "Tasks"
        alt.mkdir(parents=True)
        (alt / "a.md").write_text(NOTE.format(slug="a", status="active", repo=""))
        (alt / ".active").write_text("a\n")
        out = self.run_hook({"session_id": "x", "cwd": "/"}, env_extra={"CLAUDE_PLUGIN_OPTION_VAULTPATH": "~/alt"})
        self.assertIn("Active task: a (global)", out)

    def test_no_vault_prints_only_the_time(self):
        shutil.rmtree(self.home / "vault")
        out = self.run_hook({"session_id": "x", "cwd": "/"})
        self.assertRegex(out, r"^Now: .+\n$")

    def test_no_task_hint_uses_prefixed_skill(self):
        out = self.run_hook({"session_id": "x", "cwd": "/"})
        self.assertIn("/tasks:task-start", out)

    def _escaping_active(self):
        outside = self.home / "outside"
        outside.mkdir()
        (outside / "secret.md").write_text("## Next\n- AWS_SECRET=abc123\n")
        (self.tasks / ".active").write_text("../../outside/secret\n")

    def test_an_active_slug_that_escapes_tasks_is_ignored(self):
        self._escaping_active()
        out = self.run_hook({"session_id": "x", "cwd": "/"})
        self.assertIn("No active task", out)
        self.assertNotIn("AWS_SECRET", out)

    def test_without_python_an_escaping_active_slug_is_ignored(self):
        self._escaping_active()
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        for tool in ("bash", "date", "tr", "awk", "head", "cat", "dirname"):
            os.symlink(shutil.which(tool), bin_dir / tool)
        out = self.run_hook(stdin=subprocess.DEVNULL, env_extra={"PATH": str(bin_dir)})
        self.assertIn("Vault:", out)
        self.assertIn("No active task", out)
        self.assertNotIn("AWS_SECRET", out)

    def test_vault_line_names_the_resolved_vault_even_with_no_task(self):
        (self.home / "alt" / "Tasks").mkdir(parents=True)
        out = self.run_hook({"session_id": "x", "cwd": "/"}, env_extra={"CLAUDE_PLUGIN_OPTION_VAULTPATH": "~/alt"})
        self.assertIn(f"Vault: {self.home / 'alt'}\n", out)
        self.assertIn("No active task", out)


CASES = HOOK.parent.parent.parent / "task-track" / "tests" / "fixtures" / "vault-cases.ts"
MARK = "export const CASES: readonly VaultCase[] = "


class SharedVaultCasesTest(unittest.TestCase):
    """The cases tests/task-track.test.ts also runs against resolve.ts: the two resolvers must agree."""

    def test_every_shared_case(self):
        cases = json.loads(CASES.read_text().split(MARK, 1)[1])
        self.assertGreater(len(cases), 15)
        for case in cases:
            with self.subTest(case["name"]):
                home = pathlib.Path(tempfile.mkdtemp())
                try:
                    self.check(home, case, self.run_case(home, case))
                finally:
                    shutil.rmtree(home)

    def run_case(self, home, case):
        if case["config"] is not None:
            cfg = home / ".config" / "adhd-planner" / "vaults.json"
            cfg.parent.mkdir(parents=True)
            cfg.write_text(case["config"] if isinstance(case["config"], str) else json.dumps(case["config"]))
        base = time.time() - 1000
        for rel, v in case["vaults"].items():
            tasks = home / rel / "Tasks"
            tasks.mkdir(parents=True)
            for slug, n in v.get("notes", {}).items():
                p = tasks / f"{slug}.md"
                p.write_text(NOTE.format(slug=slug, status=n.get("status", "active"),
                                         repo=f"repo: {n['repo']}\n" if n.get("repo") else ""))
                os.utime(p, (base + n.get("mtime", 0),) * 2)
            if "active" in v:
                (tasks / ".active").write_text(v["active"] + "\n")
            if "session" in v:
                (tasks / ".session").mkdir()
                s = tasks / ".session" / "s1"
                s.write_text(v["session"]["slug"] + "\n")
                os.utime(s, (base + v["session"].get("mtime", 0),) * 2)
        cwd = str(home) + case["cwd"][1:]
        env = {"HOME": str(home), "PATH": os.environ["PATH"]}
        out = subprocess.run(["bash", str(HOOK)], input=json.dumps({"session_id": "s1", "cwd": cwd}).encode(),
                             env=env, capture_output=True, timeout=10, check=True)
        return out.stdout.decode()

    def check(self, home, case, out):
        want = case["expect"]
        if "error" in want:
            self.assertIn("Vault config error: ", out)
            self.assertIn(want["error"], out)
        else:
            self.assertNotIn("Vault config error", out)
        if "skipped" in want:
            self.assertIn(f"(skipped vault {want['skipped']}: no Tasks/ at ", out)
        if want["vault"] is None:
            self.assertNotIn("Vault:", out)
            return
        self.assertIn(f"Vault: {home}{want['vault'][1:]}\n", out)
        if want["slug"]:
            self.assertIn(f"Active task: {want['slug']} ({want['reason']}) — full note: ", out)
        else:
            self.assertIn("No active task", out)
        if "nameLine" in want:
            self.assertIn(want["nameLine"] + "\n", out)
        if case["config"] is None or "error" in want:
            self.assertNotIn("Vault name:", out)


if __name__ == "__main__":
    unittest.main()


class ResolverErrorTest(unittest.TestCase):
    """A resolver error with vaults.json in use: named in the reason, or on its own line when no task can be shown."""

    def setUp(self):
        self.assertNotEqual(os.geteuid(), 0, "run as non-root: root reads mode 000 files")
        self.home = pathlib.Path(tempfile.mkdtemp())
        cfg = self.home / ".config" / "adhd-planner" / "vaults.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text(json.dumps({"default": "personal", "vaults": {
            "personal": {"path": "~/vault"}, "work": {"path": "~/work"}}}))

    def tearDown(self):
        shutil.rmtree(self.home)

    def vault_with_unreadable_override(self, rel):
        tasks = self.home / rel / "Tasks"
        (tasks / ".session").mkdir(parents=True)
        (tasks / "g.md").write_text(NOTE.format(slug="g", status="active", repo=""))
        (tasks / ".active").write_text("g\n")
        override = tasks / ".session" / "s1"
        override.write_text("g\n")
        override.chmod(0)
        return override

    def run_hook(self, *overrides):
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"]}
        try:
            out = subprocess.run(["bash", str(HOOK)], input=json.dumps({"session_id": "s1", "cwd": str(self.home)}).encode(),
                                 env=env, capture_output=True, timeout=10, check=True)
        finally:
            for o in overrides:
                o.chmod(0o600)
        return out.stdout.decode()

    def test_the_reason_says_default_when_vaults_json_is_in_use(self):
        out = self.run_hook(self.vault_with_unreadable_override("vault"))
        self.assertIn("Active task: g (default (resolver error: PermissionError", out)

    def test_an_unusable_default_vault_still_names_the_error(self):
        out = self.run_hook(self.vault_with_unreadable_override("work"))
        self.assertIn("(skipped vault personal: no Tasks/ at ", out)
        self.assertIn("Task resolver error: PermissionError: ", out)
        self.assertNotIn("Active task:", out)
