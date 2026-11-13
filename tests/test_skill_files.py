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


SHARED_BLOCK = re.compile(r"<!-- shared: where-this-runs -->.*?<!-- /shared: where-this-runs -->", re.S)


def outside_shared(text):
    """text without its shared `where-this-runs` block; fails when the block is missing."""
    rest, n = SHARED_BLOCK.subn("", text)
    assert n == 1, f"expected one shared where-this-runs block, found {n}"
    return rest


class PlanWeekTest(unittest.TestCase):
    def test_hands_off_week_tasks_files(self):
        text = skill("plan-week")
        self.assertIn("tools/out/week-tasks-<date>.json", text)
        self.assertNotIn("tools/out/tasks-<date>.json", text)

    def test_interactive_run_lets_the_tool_pick_the_week(self):
        self.assertNotIn("--week-start <YYYY-MM-DD>", skill("plan-week"))

    def test_vault_run_uses_the_queue_and_keeps_its_order(self):
        text = flat(skill("plan-week"))
        own = flat(outside_shared(skill("plan-week")))
        self.assertIn('tools/task_queue.py --vault "<name>=<vault-path>"', own)
        self.assertIn("Wrote <path>", own)
        self.assertIn("--keep-order", text)
        self.assertIn("not_placed", text)
        self.assertNotIn("--out", text)
        self.assertNotIn("estimate when an item has none", text)

    def test_vault_block_checks_for_a_stale_tools_folder_first(self):
        text = flat(skill("plan-week"))
        check = ("If `<planner-path>/tools/task_queue.py` is missing, the folder's tools predate this "
                 "plugin version: say so, offer `planner:setup`, and stop. Do not build the task list by hand.")
        self.assertIn("In this skill: - " + check, text)

    def test_queue_rows_are_not_decomposed(self):
        self.assertIn("Rows from `task_queue.py` are not decomposed here.", flat(skill("plan-week")))


class DailySkillsQueueTest(unittest.TestCase):
    DAILY = ("plan-day", "morning-startup", "eod-shutdown")
    CHECK = ("If `<planner-path>/tools/task_queue.py` is missing, the folder's tools predate this "
             "plugin version: say so, offer `planner:setup`, and stop. Do not build the task list by hand.")

    def test_daily_skills_run_the_queue_for_a_day(self):
        for name in self.DAILY:
            with self.subTest(skill=name):
                text = flat(skill(name))
                own = flat(outside_shared(skill(name)))
                self.assertIn('tools/task_queue.py --vault "<name>=<vault-path>"', own)
                self.assertIn("--date <", own)
                self.assertIn("Wrote <path>", own)
                self.assertNotIn("--out", text)

    def test_daily_skills_show_ten_rows_and_what_was_left_out(self):
        for name in self.DAILY:
            with self.subTest(skill=name):
                text = flat(skill(name))
                self.assertIn("first ten rows", text)
                self.assertIn("not_placed", text)
                self.assertIn("(overdue)", text)

    def test_daily_skills_check_for_a_stale_tools_folder_first(self):
        for name in self.DAILY:
            with self.subTest(skill=name):
                self.assertIn("In this skill: - " + self.CHECK, flat(skill(name)))


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


    def test_week_plan_vault_rows_are_left_out(self):
        self.assertEqual(flat(skill("morning-startup")).count('"source": "vault"'), 2)

    def test_older_week_plans_are_asked_about(self):
        self.assertIn("older week plans", flat(skill("morning-startup")))


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

    def test_template_carries_priority_and_due_after_up(self):
        text = (ROOT / "examples" / "vault-starter" / "Templates" / "Task.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^up:.*\npriority: p3\ndue:[ \t]*$")
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

    def test_new_task_skills_write_priority_and_due(self):
        for name in ("create-task", "task-start"):
            text = flat(task_skill(name))
            with self.subTest(skill=name):
                self.assertIn("`priority`", text)
                self.assertIn("`due`", text)
                self.assertIn("p3", text)

    def test_create_task_defaults_priority_without_asking(self):
        text = flat(task_skill("create-task"))
        self.assertIn("writes `priority: p3` without asking", text)
        self.assertIn("one working day", text)

    def test_task_note_sets_priority_or_due_with_a_log_line(self):
        text = flat(task_skill("task-note"))
        self.assertIn("`priority`", text)
        self.assertIn("`due`", text)
        self.assertIn("`p0`..`p5`", text)
        self.assertIn("priority p3 → p1", text)
        self.assertIn("due (none) → 2026-11-20", text)
        self.assertIn("→ (none)", text)
        self.assertIn("writes nothing", text)

    def test_task_finish_sets_done_and_finished_and_clears_sessions(self):
        text = flat(task_skill("task-finish"))
        for phrase in ("status: done", "finished: <today>", "Tasks/.session/", "Tasks/.active", "finished: <outcome>"):
            self.assertIn(phrase, text)


STARTER = ROOT / "examples" / "vault-starter"
HUBS = ("Templates/Project.md", "Projects/ADHD Planner.md", "Areas/Health.md")
OLD_TASKS_POINTER = "Tasks link here via `up:` — see the backlinks pane, or [[Tasks.base]]."


def tasks_section(text):
    """From the `## Tasks` heading to the next `## ` heading or the end of the file."""
    found = re.search(r"(?ms)^## Tasks\n(.*?)(?=^## |\Z)", text)
    return found.group(1) if found else None


class HubTasksBaseTest(unittest.TestCase):
    def test_hubs_drop_the_old_pointer(self):
        for name in HUBS:
            with self.subTest(hub=name):
                self.assertNotIn(OLD_TASKS_POINTER, (STARTER / name).read_text(encoding="utf-8"))

    def test_hubs_have_a_base_fence_under_tasks(self):
        for name in HUBS:
            with self.subTest(hub=name):
                section = tasks_section((STARTER / name).read_text(encoding="utf-8"))
                self.assertIsNotNone(section)
                self.assertTrue(section.strip().startswith("```base\n"), section)
                self.assertTrue(section.strip().endswith("```"), section)

    def test_block_filters_on_up_not_any_link(self):
        # Step 0 (f): file.hasLink(this.file) listed a task under a hub its body only mentions.
        for name in HUBS:
            with self.subTest(hub=name):
                section = tasks_section((STARTER / name).read_text(encoding="utf-8"))
                for phrase in ('file.inFolder("Tasks")', "up == this.file.asLink()", 'status != "done"',
                               '"p3")', 'date("9999-12-31")', 'today() + "7 days"'):
                    self.assertIn(phrase, section)
                self.assertNotIn("file.hasLink", section)

    def test_hubs_share_the_template_block(self):
        template = tasks_section((STARTER / HUBS[0]).read_text(encoding="utf-8"))
        for name in HUBS[1:]:
            with self.subTest(hub=name):
                self.assertEqual(tasks_section((STARTER / name).read_text(encoding="utf-8")), template)

    def test_vault_guide_explains_priority(self):
        text = flat((STARTER / "Notes" / "How this vault works.md").read_text(encoding="utf-8"))
        for phrase in ("priority:", "due:", "p0", "p5", "p3", "task-note"):
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
