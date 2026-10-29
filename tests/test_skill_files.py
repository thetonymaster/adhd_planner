"""The planner skills hand each other the files the tools write.
Run: python3 -m unittest tests.test_skill_files
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = ROOT / "plugins" / "planner" / "skills"
TASK_SKILLS = ROOT / "plugins" / "tasks" / "skills"


def skill(name):
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def flat(text):
    """One line, `> ` quote markers dropped, so a phrase wrapped across lines still matches."""
    return re.sub(r"\s+", " ", re.sub(r"(?m)^>\s?", "", text))


class PlanWeekTest(unittest.TestCase):
    def test_hands_off_week_tasks_files(self):
        text = skill("plan-week")
        self.assertIn("tools/out/week-tasks-<date>.json", text)
        self.assertNotIn("tools/out/tasks-<date>.json", text)

    def test_interactive_run_lets_the_tool_pick_the_week(self):
        self.assertNotIn("--week-start <YYYY-MM-DD>", skill("plan-week"))


class MorningStartupTest(unittest.TestCase):
    POOL = r"write the merged pool to `tools/out/tasks-<today>\.json`"

    def test_steps_and_scheduled_prompt_write_the_pool(self):
        self.assertEqual(len(re.findall(self.POOL, flat(skill("morning-startup")), re.IGNORECASE)), 2)

    def test_plan_day_reads_the_pool(self):
        found = re.findall(r"plan_day\.py --tasks (\S+)", flat(skill("morning-startup")))
        self.assertEqual(found, ["tools/out/tasks-<today>.json"] * 2)

    def test_the_pool_includes_the_week_plan(self):
        self.assertEqual(flat(skill("morning-startup")).count("tools/out/week-tasks-<today>.json"), 2)

    def test_yesterdays_pool_needs_last_nights_triage(self):
        text = flat(skill("morning-startup"))
        self.assertEqual(text.count("`tools/out/triage-<yesterday>.md` exists"), 2)
        # Name the file it is compared with: "at least as new as it" was ambiguous.
        self.assertEqual(text.count("at least as new as `tools/out/tasks-<yesterday>.json`"), 2)

    def test_a_rerun_does_not_merge_the_previous_pool(self):
        # Same day, no new captures: tasks-<today>.json may be this morning's merged pool, not triage output.
        self.assertIn("`tools/out/tasks-<today>.json` (only if `tools/out/triage-<today>.md` exists and is "
                      "at least as new as `tools/out/tasks-<today>.json`", flat(skill("morning-startup")))


class HabitTrackerTest(unittest.TestCase):
    def test_log_no_longer_claims_to_record_the_whole_day(self):
        text = flat(skill("habit-tracker"))
        self.assertNotIn("So log once", text)
        self.assertNotIn("records the **whole day**", text)
        self.assertIn("can't un-mark", text)


def task_skill(name):
    return (TASK_SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


class TaskLifecycleTest(unittest.TestCase):
    def test_template_defaults_to_parked_with_finished_field(self):
        text = (ROOT / "examples" / "vault-starter" / "Templates" / "Task.md").read_text(encoding="utf-8")
        self.assertIn("status: parked", text)
        self.assertNotIn("status: active", text)
        self.assertRegex(text, r"(?m)^started:.*\nfinished:")

    def test_task_start_sets_active_explicitly(self):
        self.assertIn("status: active", task_skill("task-start"))

    def test_task_park_always_parks(self):
        text = flat(task_skill("task-park"))
        self.assertIn("status: parked", text)
        self.assertNotIn("If the user is switching or stopping", text)
        self.assertNotIn("or `done` if finished", text)
        self.assertIn("/tasks:task-finish", text)

    def test_create_task_never_binds_the_session(self):
        text = flat(task_skill("create-task"))
        self.assertIn("status: parked", text)
        self.assertIn("Never writes `Tasks/.active` or `Tasks/.session/`", text)

    def test_task_finish_sets_done_and_finished_and_clears_sessions(self):
        text = flat(task_skill("task-finish"))
        for phrase in ("status: done", "finished: <today>", "Tasks/.session/", "Tasks/.active", "finished: <outcome>"):
            self.assertIn(phrase, text)


def description(path):
    """The frontmatter description, a folded `>` block joined to one line."""
    front = path.read_text(encoding="utf-8").split("---")[1]
    found = re.search(r"(?ms)^description:[ \t]*(?:>-?|\|)?[ \t]*\n?(.*?)(?=^\S|\Z)", front)
    return re.sub(r"\s+", " ", found.group(1)).strip()


class SkillDescriptionLengthTest(unittest.TestCase):
    LIMIT = 400  # what 01c329b trimmed to so every skill fits Claude Code's skill listing

    def test_every_description_fits_the_listing(self):
        paths = sorted(ROOT.glob("plugins/*/skills/*/SKILL.md"))
        self.assertTrue(paths)
        for path in paths:
            text = description(path)
            with self.subTest(skill=str(path.relative_to(ROOT))):
                self.assertTrue(text)
                self.assertLessEqual(len(text), self.LIMIT, text)


if __name__ == "__main__":
    unittest.main()
