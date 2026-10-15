"""The planner skills hand each other the files the tools write.
Run: python3 -m unittest tests.test_skill_files
"""
import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "planner" / "skills"


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


if __name__ == "__main__":
    unittest.main()
