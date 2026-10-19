"""The `Now:` lines of the tasks hooks follow vaults.json's timezone, then $TZ, then the system clock.

Run: python3 -m unittest tests.test_now
"""
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
import zoneinfo

HOOKS = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "tasks" / "hooks"
LOAD_TASK = HOOKS / "load-task.sh"
# Both hooks print the date too: skills take today from the latest `Now:` line, which may come after midnight.
FULL = "%a %Y-%m-%d %H:%M"


def prompt_command() -> str:
    """The UserPromptSubmit command exactly as hooks.json ships it."""
    hooks = json.loads((HOOKS / "hooks.json").read_text())["hooks"]["UserPromptSubmit"]
    (command,) = [h["command"] for group in hooks for h in group["hooks"]]
    return command


class NowLineTest(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)
        (self.home / "vault" / "Tasks").mkdir(parents=True)

    def write_config(self, **extra):
        cfg = self.home / ".config" / "adhd-planner" / "vaults.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({**extra, "default": "personal", "vaults": {"personal": {"path": "~/vault"}}}))

    def env(self, **extra):
        return {"HOME": str(self.home), "PATH": os.environ["PATH"], "CLAUDE_PLUGIN_ROOT": str(HOOKS.parent), **extra}

    def run_session_start(self, env):
        out = subprocess.run(["bash", str(LOAD_TASK)], input=b'{"session_id": "s1", "cwd": "/"}', env=env,
                             capture_output=True, timeout=10, check=True)
        return out.stdout.decode()

    def run_prompt_hook(self, env):
        out = subprocess.run(["bash", "-c", prompt_command()], env=env, capture_output=True, timeout=10, check=True)
        return out.stdout.decode()

    def assert_now(self, run, zone, fmt):
        """The hook's first line is `Now: <fmt>` in `zone`, read just before or just after it ran."""
        before = datetime.datetime.now(zoneinfo.ZoneInfo(zone)).strftime(fmt)
        out = run()
        after = datetime.datetime.now(zoneinfo.ZoneInfo(zone)).strftime(fmt)
        first = out.splitlines()[0]
        self.assertIn(first, {f"Now: {before}", f"Now: {after}"}, out)

    def test_session_start_uses_the_vaults_json_zone_over_tz(self):
        self.write_config(timezone="Asia/Tokyo")
        self.assert_now(lambda: self.run_session_start(self.env(TZ="UTC")), "Asia/Tokyo", "%a %Y-%m-%d %H:%M")

    def test_prompt_hook_uses_the_vaults_json_zone_over_tz(self):
        self.write_config(timezone="Asia/Tokyo")
        self.assert_now(lambda: self.run_prompt_hook(self.env(TZ="UTC")), "Asia/Tokyo", FULL)

    def test_without_a_zone_both_follow_tz(self):
        self.write_config()
        env = self.env(TZ="Pacific/Kiritimati")
        self.assert_now(lambda: self.run_session_start(env), "Pacific/Kiritimati", "%a %Y-%m-%d %H:%M")
        self.assert_now(lambda: self.run_prompt_hook(env), "Pacific/Kiritimati", FULL)

    def test_session_start_prints_now_once(self):
        self.write_config(timezone="Asia/Tokyo")
        out = self.run_session_start(self.env())
        self.assertEqual(sum(line.startswith("Now: ") for line in out.splitlines()), 1, out)

    def test_without_python_both_fall_back_to_date(self):
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        for tool in ("bash", "date", "tr", "awk", "head", "cat", "dirname"):
            os.symlink(shutil.which(tool), bin_dir / tool)
        self.write_config(timezone="Asia/Tokyo")
        env = self.env(PATH=str(bin_dir), TZ="Pacific/Kiritimati")
        self.assert_now(lambda: self.run_session_start(env), "Pacific/Kiritimati", "%a %Y-%m-%d %H:%M")
        self.assert_now(lambda: self.run_prompt_hook(env), "Pacific/Kiritimati", FULL)


if __name__ == "__main__":
    unittest.main()
