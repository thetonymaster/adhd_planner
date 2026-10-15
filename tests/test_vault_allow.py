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
        self.assertEqual(out["decision"], {"behavior": "allow"})

    def test_read_inside_vault_is_allowed(self):
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "Tasks" / "a.md")}))

    def test_edit_write_grep_inside_are_allowed(self):
        self.assertAllowed(self.ask("Edit", {"file_path": str(self.vault / "x.md")}))
        self.assertAllowed(self.ask("Write", {"file_path": str(self.vault / "new" / "y.md")}))
        self.assertAllowed(self.ask("Write", {"file_path": str(self.vault / "board.canvas")}))
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": str(self.vault), "glob": "Projects/*.md"}))

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
        self.assertAllowed(result)

    def test_glob_pattern_escaping_the_vault_is_left_to_the_user(self):
        self.assertIsNone(self.ask("Glob", {"pattern": "/etc/**"}, cwd=str(self.vault)))
        self.assertIsNone(self.ask("Glob", {"pattern": "../../**", "path": str(self.vault / "Tasks")}))
        self.assertIsNone(self.ask("Glob", {"pattern": "~/**"}, cwd=str(self.vault)))

    def test_grep_glob_escaping_the_vault_is_left_to_the_user(self):
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.vault), "glob": "/etc/*"}))
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": str(self.vault), "glob": "Projects/*.md"}))

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

    def test_a_path_in_the_second_vault_is_allowed(self):
        work, env = self.two_vaults()
        result = self.ask("Read", {"file_path": str(work / "Tasks" / "w.md")}, env_extra=env)
        self.assertAllowed(result)
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "a.md")}, env_extra=env))

    def test_a_search_spanning_two_vaults_is_left_to_the_user(self):
        _, env = self.two_vaults()
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.home)}, env_extra=env))

    def test_a_symlinked_second_vault_is_resolved(self):
        real = self.home / "icloud" / "work"
        (real / "Tasks").mkdir(parents=True)
        os.symlink(real, self.home / "w")
        _, env = self.two_vaults(work_path=self.home / "w")
        result = self.ask("Read", {"file_path": str(real / "x.md")}, env_extra=env)
        self.assertAllowed(result)

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

    def test_a_vault_nested_in_another_is_allowed(self):
        inner, env = self.two_vaults(work_path=self.vault / "work")
        result = self.ask("Read", {"file_path": str(inner / "Tasks" / "w.md")}, env_extra=env)
        self.assertAllowed(result)

    def test_a_prefix_sibling_of_a_registered_vault_is_outside(self):
        _, env = self.two_vaults()
        (self.home / "work-evil").mkdir()
        self.assertIsNone(self.ask("Read", {"file_path": str(self.home / "work-evil" / "a.md")}, env_extra=env))

    def test_writes_that_can_run_code_or_steer_claude_are_left_to_the_user(self):
        for rel in (".git/config", ".git/hooks/pre-commit", ".claude/settings.json",
                    ".obsidian/plugins/p/main.js", "CLAUDE.md", "Projects/CLAUDE.md",
                    "scripts/x.sh", "n.ipynb", ".obsidian/notes.md"):
            with self.subTest(rel):
                self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / rel)}))
                self.assertIsNone(self.ask("Edit", {"file_path": str(self.vault / rel)}))
        self.assertIsNone(self.ask("NotebookEdit", {"notebook_path": str(self.vault / "n.ipynb")}))

    def test_task_state_files_are_writable(self):
        for rel in ("Tasks/.active", "Tasks/.pomo.json", "Tasks/.session/abc-123"):
            with self.subTest(rel):
                self.assertAllowed(self.ask("Write", {"file_path": str(self.vault / rel)}))
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / "Tasks" / ".session" / "a" / "b")}))
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / "Tasks" / ".other")}))
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / "Notes" / ".active")}))

    def test_reads_skip_dot_paths(self):
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "Notes" / "a.md")}))
        self.assertAllowed(self.ask("Read", {"file_path": str(self.vault / "attachments" / "x.png")}))
        self.assertIsNone(self.ask("Read", {"file_path": str(self.vault / ".obsidian" / "plugins" / "p" / "data.json")}))
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.vault / ".git")}))

    def test_a_dot_inside_a_segment_is_not_hidden(self):
        self.assertAllowed(self.ask("Write", {"file_path": str(self.vault / "Projects" / "v1.2" / "plan.md")}))

    def test_the_vault_root_itself_is_searchable_not_writable(self):
        self.assertAllowed(self.ask("Glob", {"pattern": "**/*.md", "path": str(self.vault)}))
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault)}))

    def test_notes_in_a_symlinked_vault_are_writable(self):
        real = self.home / "icloud" / "vault"
        real.mkdir(parents=True)
        os.symlink(real, self.home / "v")
        env = {"CLAUDE_PLUGIN_OPTION_VAULTPATH": "~/v"}
        self.assertAllowed(self.ask("Write", {"file_path": str(self.home / "v" / "a.md")}, env_extra=env))
        self.assertIsNone(self.ask("Write", {"file_path": str(self.home / "v" / ".git" / "config")}, env_extra=env))

    def test_claude_memory_files_are_refused_in_any_case(self):
        for rel in ("Projects/claude.md", "Claude.md", "CLAUDE.local.md", "Projects/Claude.Local.md"):
            with self.subTest(rel):
                self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / rel)}))

    def test_a_symlink_to_a_dot_path_is_refused(self):
        (self.vault / ".git").mkdir()
        os.symlink(self.vault / ".git" / "config", self.vault / "notes-link.md")
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / "notes-link.md")}))

    def test_edit_of_a_session_pointer_is_allowed(self):
        self.assertAllowed(self.ask("Edit", {"file_path": str(self.vault / "Tasks" / ".session" / "abc")}))

    def test_home_root_and_ancestors_are_never_a_vault(self):
        (self.home / ".ssh").mkdir()
        for vault in (str(self.home), "/", str(self.home.parent)):
            with self.subTest(vault):
                self.assertIsNone(self.ask("Write", {"file_path": str(self.home / "notes.md")},
                                           env_extra={"VAULT": vault}))
                self.assertIsNone(self.ask("Read", {"file_path": str(self.home / ".ssh" / "id_rsa")},
                                           env_extra={"VAULT": vault}))

    def test_claude_config_is_never_a_vault(self):
        skills = self.home / ".claude" / "skills" / "x"
        skills.mkdir(parents=True)
        for vault in (str(self.home / ".claude"), str(self.home / ".claude" / "skills")):
            with self.subTest(vault):
                self.assertIsNone(self.ask("Write", {"file_path": str(skills / "SKILL.md")},
                                           env_extra={"VAULT": vault}))
        custom = self.home / "cfg"
        (custom / "rules").mkdir(parents=True)
        self.assertIsNone(self.ask("Write", {"file_path": str(custom / "rules" / "r.md")},
                                   env_extra={"VAULT": str(custom), "CLAUDE_CONFIG_DIR": str(custom)}))

    def test_a_literal_tilde_claude_config_dir_inside_the_vault_makes_it_untrusted(self):
        (self.vault / "cfg" / "commands").mkdir(parents=True)
        # settings.json `env` does not expand `~`; Claude Code may read it either way.
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / "cfg" / "commands" / "x.md")},
                                   env_extra={"CLAUDE_CONFIG_DIR": "~/vault/cfg"}))
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / "a.md")},
                                   env_extra={"CLAUDE_CONFIG_DIR": "~/vault/cfg"}))

    def test_a_relative_implicit_vault_approves_nothing(self):
        project = self.home / "project"
        project.mkdir()
        self.assertIsNone(self.ask_from(project, "Write", {"file_path": str(project / "a.md")}, {"VAULT": "."}))

    def test_a_vaults_json_inside_a_vault_approves_nothing(self):
        cfg = self.vault / "vaults.json"
        cfg.write_text(json.dumps({"vaults": {"personal": {"path": str(self.vault)}}}))
        env = {"ADHD_PLANNER_VAULTS": str(cfg)}
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / "a.md")}, env_extra=env))
        self.assertIsNone(self.ask("Read", {"file_path": str(cfg)}, env_extra=env))

    def test_a_broken_config_approves_nothing(self):
        cfg = self.home / "vaults.json"
        cfg.write_text("{not json")
        env = {"ADHD_PLANNER_VAULTS": str(cfg)}
        self.assertIsNone(self.ask("Read", {"file_path": str(self.vault / "a.md")}, env_extra=env))

    def test_json_that_is_not_an_object_exits_cleanly(self):
        for raw in (b"[1]", b"42", b'"x"', b"null"):
            with self.subTest(raw):
                self.assertIsNone(self.ask("Read", {}, raw=raw))

    def test_brace_or_dot_glob_patterns_are_left_to_the_user(self):
        self.assertIsNone(self.ask("Glob", {"pattern": "{..,x}/**", "path": str(self.vault)}))
        self.assertIsNone(self.ask("Glob", {"pattern": ".obsidian/**", "path": str(self.vault)}))
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.vault), "glob": "{a,../b}"}))
        self.assertAllowed(self.ask("Glob", {"pattern": "Projects/**/*.md", "path": str(self.vault)}))

    def test_grep_that_can_reach_hidden_files_is_left_to_the_user(self):
        v = str(self.vault)
        self.assertIsNone(self.ask("Grep", {"pattern": "sk-", "path": v}))
        self.assertIsNone(self.ask("Grep", {"pattern": "sk-"}, cwd=v))
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": v, "glob": "*.json"}))
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": v, "glob": "*.md.json"}))

    def test_grep_with_a_note_glob_or_a_single_note_is_allowed(self):
        v = str(self.vault)
        (self.vault / "Notes").mkdir()
        (self.vault / "Notes" / "a.md").write_text("x")
        for glob in ("Projects/*.md", "/Daily/*.md", "Areas/Work/notes.md", "Areas/*.canvas", "Areas/my-note_1.canvas"):
            with self.subTest(glob):
                self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": v, "glob": glob}))
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "glob": "Projects/*.md"}, cwd=v))
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": str(self.vault / "Notes" / "a.md")}))

    def test_grep_globs_outside_the_strict_grammar_are_left_to_the_user(self):
        v = str(self.vault)
        (self.vault / ".obsidian" / "plugins" / "x").mkdir(parents=True)
        (self.vault / ".obsidian" / "plugins" / "x" / "data.json").write_text("{}")
        for glob in ("*.md", "**/*.md", "*/*.md", "Projects/**/*.md", ".obsidian/*.md", "!x.md",
                     "*.json *.md", "*.json,*.md", "Projects/*.json", "{a,b}/*.md", "Daily Notes/*.md",
                     "Projects/[a]*.md", "Projects/.hid/*.md", "**/*.canvas", "Projects/*.md\n*.json"):
            with self.subTest(glob):
                self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": v, "glob": glob}))
                self.assertIsNone(self.ask("Grep", {"pattern": "x", "glob": glob}, cwd=v))

    def test_grep_of_a_hidden_single_file_or_missing_file_is_left_to_the_user(self):
        (self.vault / ".obsidian").mkdir()
        (self.vault / ".obsidian" / "data.json").write_text("{}")
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.vault / ".obsidian" / "data.json")}))
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.vault / "Notes" / "nope.md")}))

    def test_writes_that_plant_plugin_code_are_left_to_the_user(self):
        path = str(self.vault / "a.md")
        for marker in ("```dataviewjs\nx\n```", "hi <%* tp.file %>", "`$= 1+1`", "~~~dataviewjs\nx",
                       "``` dataviewjs\nx", "````DataviewJS\nx", "  ```dataviewjs\nx", "a\n\t~~~~ DATAVIEWJS"):
            with self.subTest(marker):
                self.assertIsNone(self.ask("Write", {"file_path": path, "content": marker}))
                self.assertIsNone(self.ask("Edit", {"file_path": path, "new_string": marker}))
        self.assertAllowed(self.ask("Write", {"file_path": path, "content": "# plain\n```dataview\nLIST\n```"}))
        self.assertAllowed(self.ask("Write", {"file_path": path, "content": "I use dataview and dataviewjs a lot"}))
        self.assertAllowed(self.ask("Edit", {"file_path": path, "old_string": "a", "new_string": "b"}))

    def test_a_fence_behind_a_markdown_container_prefix_is_still_code(self):
        path = str(self.vault / "a.md")
        for marker in ("> ```dataviewjs\nx", "> [!note]\n> ```dataviewjs\nx", "- ```dataviewjs\nx",
                       "1. ~~~dataviewjs\nx", ">> ```dataviewjs\nx", "2) ```dataviewjs\nx",
                       "  > - * ```dataviewjs\nx", "+\t```dataviewjs\nx", "\t>\t~~~~DataviewJS\nx"):
            with self.subTest(marker):
                self.assertIsNone(self.ask("Write", {"file_path": path, "content": marker}))
                self.assertIsNone(self.ask("Edit", {"file_path": path, "new_string": marker}))
        quiet = "# t\n> quote about dataviewjs\n- item\n1. step\n> - nested\n"
        self.assertAllowed(self.ask("Write", {"file_path": path, "content": quiet}))

    def test_grep_glob_that_could_match_a_hidden_note_is_left_to_the_user(self):
        v = str(self.vault)
        (self.vault / "Projects").mkdir()
        (self.vault / "Projects" / "a.md").write_text("x")
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": v, "glob": "Projects/*.md"}))
        (self.vault / "Projects" / ".secret.md").write_text("x")
        for glob in ("Projects/*.md", "/Projects/*.md"):
            with self.subTest(glob):
                self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": v, "glob": glob}))
                self.assertIsNone(self.ask("Grep", {"pattern": "x", "glob": glob}, cwd=v))
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": v, "glob": "Projects/a.md"}))
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": v, "glob": "Projects/*.canvas"}))
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.vault / "Projects"), "glob": "*.md"}))
        self.assertAllowed(self.ask("Grep", {"pattern": "x", "path": v, "glob": "Missing/*.md"}))

    def test_a_canvas_in_a_dot_folder_is_not_writable(self):
        self.assertIsNone(self.ask("Write", {"file_path": str(self.vault / ".obsidian" / "b.canvas")}))

    def test_a_symlink_to_a_hidden_target_is_refused(self):
        (self.vault / ".obsidian").mkdir()
        (self.vault / ".obsidian" / "data.json").write_text("{}")
        os.symlink(self.vault / ".obsidian" / "data.json", self.vault / "link.md")
        self.assertIsNone(self.ask("Read", {"file_path": str(self.vault / "link.md")}))
        self.assertIsNone(self.ask("Grep", {"pattern": "x", "path": str(self.vault / "link.md")}))
