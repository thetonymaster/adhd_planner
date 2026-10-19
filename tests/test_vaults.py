"""Tests for plugins/tasks/hooks/vaults.py config parsing. Run: python3 -m unittest discover -s tests"""
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "plugins" / "tasks" / "hooks"))
import vaults  # noqa: E402

HOME = "/home/q"


def parse(data, env=None):
    text = data if isinstance(data, str) else json.dumps(data)
    return vaults.parse(text, "vaults.json", env or {}, HOME)


class ConfigTest(unittest.TestCase):
    def test_slug_or_empty_accepts_only_kebab_slugs(self):
        self.assertEqual(vaults.slug_or_empty("set-up-vault\n"), "set-up-vault")
        for bad in ("../../outside/secret", "a/b", ".hidden", "-x", "Up", "a b", "", "x.md"):
            with self.subTest(bad):
                self.assertEqual(vaults.slug_or_empty(bad), "")

    def test_two_vaults_with_folders(self):
        c = parse({"default": "personal", "vaults": {
            "personal": {"path": "~/vault"},
            "work": {"path": "~/work-vault/", "folders": ["~/work"]}}})
        self.assertEqual(c.error, "")
        self.assertFalse(c.implicit)
        self.assertEqual(c.default, "personal")
        self.assertEqual([(v.name, v.path) for v in c.vaults], [("personal", "/home/q/vault"), ("work", "/home/q/work-vault")])
        self.assertEqual(c.vaults[1].folders[0][0], "~/work")

    def test_one_vault_needs_no_default(self):
        self.assertEqual(parse({"vaults": {"main": {"path": "/v"}}}).default, "main")

    def test_errors_fall_back_to_the_implicit_vault_and_name_the_problem(self):
        cases = {
            "{not json": "vaults.json: not valid JSON (",
            json.dumps({"vaults": {}}): 'with at least one vault',
            json.dumps({"vaults": {"Work": {"path": "/w"}}}): "vault name 'Work' must be kebab-case (a-z, 0-9, -)",
            json.dumps({"vaults": {"w": {}}}): "vault 'w' has no \"path\"",
            json.dumps({"vaults": {"w": {"path": "/w", "folders": "~/x"}}}): "vault 'w': \"folders\" must be a list of paths",
            json.dumps({"vaults": {"a": {"path": "/a"}, "b": {"path": "/b"}}}): '"default" is required with 2 vaults',
            json.dumps({"default": "nope", "vaults": {"a": {"path": "/a"}}}): "\"default\" is 'nope', not one of: a",
            json.dumps({"default": "a", "vaults": {"a": {"path": "/a", "folders": ["~/code"]},
                                                   "b": {"path": "/b", "folders": ["~/code/"]}}}):
                "folder '~/code/' is listed by both 'a' and 'b'",
        }
        for text, why in cases.items():
            with self.subTest(why):
                c = vaults.parse(text, "vaults.json", {"VAULT": "~/notes"}, HOME)
                self.assertIn(why, c.error)
                self.assertTrue(c.implicit)
                self.assertEqual([(v.name, v.path) for v in c.vaults], [("default", "/home/q/notes")])

    def test_implicit_follows_option_then_env_then_home_vault(self):
        self.assertEqual(vaults.implicit({}, HOME).vaults[0].path, "/home/q/vault")
        self.assertEqual(vaults.implicit({"VAULT": "/n"}, HOME).vaults[0].path, "/n")
        self.assertEqual(vaults.implicit({"VAULT": "/n", "CLAUDE_PLUGIN_OPTION_VAULTPATH": "~/o"}, HOME).vaults[0].path, "/home/q/o")

    def test_load_config_reads_the_env_path_or_returns_implicit(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "v.json")
        self.assertTrue(vaults.load_config({"ADHD_PLANNER_VAULTS": path}, d).implicit)
        pathlib.Path(path).write_text(json.dumps({"vaults": {"x": {"path": "/x"}}}))
        self.assertEqual(vaults.load_config({"ADHD_PLANNER_VAULTS": path}, d).default, "x")
        self.assertEqual(vaults.config_path({}, "/h"), "/h/.config/adhd-planner/vaults.json")

    def test_the_env_path_expands_tilde_and_a_relative_one_is_an_error(self):
        d = tempfile.mkdtemp()
        pathlib.Path(d, "v.json").write_text(json.dumps({"vaults": {"x": {"path": "/x"}}}))
        self.assertEqual(vaults.load_config({"ADHD_PLANNER_VAULTS": "~/v.json"}, d).default, "x")
        c = vaults.load_config({"ADHD_PLANNER_VAULTS": "v.json"}, d)
        self.assertTrue(c.implicit)
        self.assertIn("$ADHD_PLANNER_VAULTS must be an absolute path or start with ~/, got 'v.json'", c.error)


class FrontmatterTest(unittest.TestCase):
    def test_an_empty_field_does_not_read_the_next_line(self):
        block = "status: active\nrepo:\nstarted: 2026-10-01"
        self.assertEqual(vaults._field(block, "repo"), "")
        self.assertEqual(vaults._field(block, "status"), "active")

    def test_an_empty_repo_note_binds_no_folder(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = pathlib.Path(root) / "Tasks"
            tasks.mkdir()
            (tasks / "t.md").write_text("---\nstatus: active\nrepo: \nstarted: ~/code\n---\n# T\n")
            state, skipped = vaults.read_state(vaults.Vault("v", root), "")
            self.assertEqual(skipped, [])
            self.assertEqual([(n.slug, n.repo, n.status) for n in state.notes], [("t", "", "active")])

    def test_quotes_and_crlf_still_read(self):
        self.assertEqual(vaults._field('repo: "~/x"', "repo"), "~/x")
        self.assertEqual(vaults._field("repo:\t~/x\r", "repo"), "~/x")


if __name__ == "__main__":
    unittest.main()


class ZoneTest(unittest.TestCase):
    def test_zone_for_rejects_a_tz_in_the_wrong_case(self):
        config = vaults.implicit({}, "/home/q")
        self.assertEqual(vaults.zone_for(config, {"TZ": "Europe/Madrid"}), "Europe/Madrid")
        self.assertEqual(vaults.zone_for(config, {"TZ": "europe/madrid"}), "")
        self.assertEqual(vaults.zone_for(config, {"TZ": "Not/AZone"}), "")
