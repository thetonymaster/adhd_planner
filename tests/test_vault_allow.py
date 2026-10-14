"""Tests for plugins/tasks/hooks/vault-allow.py. Run: python3 -m unittest discover -s tests"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "tasks" / "hooks" / "vault-allow.py"


class VaultAllowTest(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp()).resolve()
        self.vault = self.home / "vault"
        (self.vault / "Tasks").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.home)

    def ask(self, tool, tool_input, cwd="/", env_extra=None, raw=None):
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"], **(env_extra or {})}
        data = raw if raw is not None else json.dumps(
            {"hook_event_name": "PermissionRequest", "tool_name": tool, "tool_input": tool_input, "cwd": cwd}).encode()
        out = subprocess.run([str(HOOK)], input=data, env=env, capture_output=True, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    def assertAllowed(self, result):
        self.assertIsNotNone(result)
        out = result["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PermissionRequest")
        self.assertEqual(out["decision"]["behavior"], "allow")
        self.assertEqual(out["decision"]["updatedPermissions"],
                         [{"type": "addDirectories", "directories": [str(self.vault)], "destination": "session"}])

    def test_read_inside_vault_is_allowed(self):
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "Tasks" / "a.md")}))

    def test_edit_write_notebook_grep_inside_are_allowed(self):
        self.assertAllowed(self.ask("Edit", {"file_path": str(self.vault / "x.md")}))
        self.assertAllowed(self.ask("Write", {"file_path": str(self.vault / "new" / "y.md")}))
        self.assertAllowed(self.ask("NotebookEdit", {"notebook_path": str(self.vault / "n.ipynb")}))
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": str(self.vault)}))

    def test_outside_vault_is_left_to_the_user(self):
        self.assertIsNone(self.ask("Read", {"file_path": str(self.home / "secrets.txt")}))

    def test_sibling_prefix_is_outside(self):
        (self.home / "vault-old").mkdir()
        self.assertIsNone(self.ask("Read", {"file_path": str(self.home / "vault-old" / "a.md")}))

    def test_dotdot_escape_is_outside(self):
        self.assertIsNone(self.ask("Read", {"file_path": str(self.vault / ".." / "secrets.txt")}))

    def test_symlink_out_of_vault_is_outside(self):
        (self.home / "outside").mkdir()
        os.symlink(self.home / "outside", self.vault / "link")
        self.assertIsNone(self.ask("Read", {"file_path": str(self.vault / "link" / "a.md")}))

    def test_bash_is_never_approved(self):
        self.assertIsNone(self.ask("Bash", {"command": f"cat {self.vault}/Tasks/a.md"}, cwd=str(self.vault)))

    def test_unknown_tool_is_left_to_the_user(self):
        self.assertIsNone(self.ask("WebFetch", {"url": "https://example.com"}, cwd=str(self.vault)))

    def test_glob_without_path_uses_cwd(self):
        self.assertAllowed(self.ask("Glob", {"pattern": "**/*.md"}, cwd=str(self.vault / "Tasks")))
        self.assertIsNone(self.ask("Glob", {"pattern": "**/*.md"}, cwd=str(self.home)))

    def test_relative_path_resolves_against_cwd(self):
        self.assertAllowed(self.ask("Read", {"file_path": "Tasks/a.md"}, cwd=str(self.vault)))

    def test_symlinked_vault_and_tilde_option(self):
        real = self.home / "icloud" / "vault"
        real.mkdir(parents=True)
        os.symlink(real, self.home / "v")
        result = self.ask("Read", {"file_path": str(real / "a.md")},
                          env_extra={"CLAUDE_PLUGIN_OPTION_VAULTPATH": "~/v/"})
        self.assertEqual(result["hookSpecificOutput"]["decision"]["updatedPermissions"][0]["directories"], [str(real)])

    def test_glob_pattern_escaping_the_vault_is_left_to_the_user(self):
        self.assertIsNone(self.ask("Glob", {"pattern": "/etc/**"}, cwd=str(self.vault)))
        self.assertIsNone(self.ask("Glob", {"pattern": "../../**", "path": str(self.vault / "Tasks")}))
        self.assertIsNone(self.ask("Glob", {"pattern": "~/**"}, cwd=str(self.vault)))

    def test_grep_glob_escaping_the_vault_is_left_to_the_user(self):
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.vault), "glob": "/etc/*"}))
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": str(self.vault), "glob": "*.md"}))

    def test_malformed_tool_input_exits_cleanly(self):
        self.assertIsNone(self.ask("Read", "not an object"))
        self.assertIsNone(self.ask("Read", {"file_path": 42}))

    def test_missing_vault_or_bad_json_does_nothing(self):
        self.assertIsNone(self.ask("Read", {"file_path": "/tmp/a"}, env_extra={"VAULT": str(self.home / "nope")}))
        self.assertIsNone(self.ask("Read", {}, raw=b"not json"))

    def two_vaults(self, work_path=None):
        work = work_path or self.home / "work"
        (work / "Tasks").mkdir(parents=True, exist_ok=True)
        cfg = self.home / "vaults.json"
        cfg.write_text(json.dumps({"default": "personal", "vaults": {
            "personal": {"path": str(self.vault)}, "work": {"path": str(work)}}}))
        return work, {"ADHD_PLANNER_VAULTS": str(cfg)}

    def test_a_path_in_the_second_vault_adds_that_vault(self):
        work, env = self.two_vaults()
        result = self.ask("Read", {"file_path": str(work / "Tasks" / "w.md")}, env_extra=env)
        self.assertEqual(result["hookSpecificOutput"]["decision"]["updatedPermissions"][0]["directories"], [str(work)])
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "a.md")}, env_extra=env))

    def test_a_search_spanning_two_vaults_is_left_to_the_user(self):
        _, env = self.two_vaults()
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.home)}, env_extra=env))

    def test_symlinked_second_vault_is_resolved(self):
        real = self.home / "icloud" / "work"
        (real / "Tasks").mkdir(parents=True)
        os.symlink(real, self.home / "w")
        _, env = self.two_vaults(work_path=self.home / "w")
        result = self.ask("Read", {"file_path": str(real / "x.md")}, env_extra=env)
        self.assertEqual(result["hookSpecificOutput"]["decision"]["updatedPermissions"][0]["directories"], [str(real)])

    def test_a_broken_config_uses_only_the_single_vault(self):
        cfg = self.home / "vaults.json"
        cfg.write_text("{not json")
        (self.home / "work" / "Tasks").mkdir(parents=True)
        env = {"ADHD_PLANNER_VAULTS": str(cfg)}
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "a.md")}, env_extra=env))
        self.assertIsNone(self.ask("Read", {"file_path": str(self.home / "work" / "a.md")}, env_extra=env))

    def ask_from(self, process_cwd, tool, tool_input, env_extra):
        """Like ask, with the hook process itself started in `process_cwd` (where a relative path would land)."""
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"], **env_extra}
        data = json.dumps({"hook_event_name": "PermissionRequest", "tool_name": tool,
                           "tool_input": tool_input, "cwd": str(process_cwd)}).encode()
        out = subprocess.run([str(HOOK)], input=data, env=env, cwd=process_cwd, capture_output=True, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    def test_a_relative_vault_path_does_not_approve_the_cwd(self):
        project = self.home / "project"
        (project / "Tasks").mkdir(parents=True)
        cfg = self.home / "vaults.json"
        cfg.write_text(json.dumps({"default": "a", "vaults": {"a": {"path": "~/vault"}, "b": {"path": "."}}}))
        env = {"ADHD_PLANNER_VAULTS": str(cfg)}
        self.assertIsNone(self.ask_from(project, "Write", {"file_path": str(project / "main.go")}, env))

    def test_a_vault_nested_in_another_approves_and_adds_the_inner_one(self):
        inner, env = self.two_vaults(work_path=self.vault / "work")
        result = self.ask("Read", {"file_path": str(inner / "Tasks" / "w.md")}, env_extra=env)
        self.assertEqual(result["hookSpecificOutput"]["decision"]["updatedPermissions"][0]["directories"], [str(inner)])

    def test_a_prefix_sibling_of_a_registered_vault_is_outside(self):
        _, env = self.two_vaults()
        (self.home / "work-evil").mkdir()
        self.assertIsNone(self.ask("Read", {"file_path": str(self.home / "work-evil" / "a.md")}, env_extra=env))
