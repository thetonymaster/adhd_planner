"""Tests for tools/task_queue.py. Run: python3 -m unittest tests.test_task_queue

Each test copies task_queue.py and planner_config.py into a temporary tools/
folder, so the tool's own tools/out/ is temporary too, then runs it as a
subprocess against temporary vault folders.
"""
import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "planner" / "tools"
sys.path.insert(0, str(TOOLS))
import planner_config  # noqa: E402
import task_queue  # noqa: E402

WEEK = "2026-11-16"  # a Monday; with --week-start the window is 16..20 Nov


def note(status="parked", up="[[Hub]]", priority="p3", due="", started="2026-11-01",
         aliases=None, heading="Heading", next_lines=("- [ ] Do it (~30 min)",),
         extra_front="", body_after=""):
    front = [f"status: {status}" if status is not None else None,
             f"up: \"{up}\"" if up is not None else None,
             f"priority: {priority}" if priority is not None else None,
             f"due: {due}" if due is not None else None,
             f"started: {started}" if started is not None else None,
             f"aliases: {aliases}" if aliases is not None else None]
    lines = ["---"] + [l for l in front if l is not None]
    if extra_front:
        lines.append(extra_front)
    lines += ["---"]
    if heading:
        lines.append(f"# {heading}")
    lines += ["", "## Goal", "Goal text.", ""]
    if next_lines is not None:
        lines.append("## Next")
        lines += list(next_lines)
        lines.append("")
    if body_after:
        lines.append(body_after)
    lines += ["## Log", "- something"]
    return "\n".join(lines) + "\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.tools = self.tmp / "planner" / "tools"
        self.tools.mkdir(parents=True)
        for f in ("task_queue.py", "planner_config.py"):
            shutil.copy(TOOLS / f, self.tools / f)
        self.out_dir = self.tools / "out"

    def vault(self, name="v", notes=None):
        root = self.tmp / "vaults" / name
        (root / "Tasks").mkdir(parents=True, exist_ok=True)
        for slug, text in (notes or {}).items():
            p = root / "Tasks" / f"{slug}.md"
            if isinstance(text, bytes):
                p.write_bytes(text)
            else:
                p.write_text(text, encoding="utf-8")
        return root

    def run_tool(self, *args, expect=0):
        r = subprocess.run([sys.executable, str(self.tools / "task_queue.py"), *map(str, args)],
                           capture_output=True, text=True, cwd=self.tmp)
        self.assertEqual(r.returncode, expect, r.stdout + r.stderr)
        return r

    @staticmethod
    def wrote(stdout):
        last = stdout.rstrip("\n").splitlines()[-1]
        assert last.startswith("Wrote "), last
        return pathlib.Path(last.removeprefix("Wrote "))

    def queue(self, notes, *args, vault_name="v"):
        """One vault with `notes`; returns (output json, stdout)."""
        root = self.vault(vault_name, notes)
        r = self.run_tool("--vault", f"{vault_name}={root}", "--week-start", WEEK, *args)
        return json.loads(self.wrote(r.stdout).read_text(encoding="utf-8")), r.stdout

    def row(self, text, slug="t"):
        data, _ = self.queue({slug: text})
        self.assertEqual(len(data["tasks"]), 1, data)
        return data["tasks"][0]

    def not_placed(self, text, slug="t"):
        data, _ = self.queue({slug: text})
        self.assertEqual(data["tasks"], [], data)
        self.assertEqual(len(data["not_placed"]), 1, data)
        return data["not_placed"][0]

    def warnings(self, text, slug="t"):
        data, _ = self.queue({slug: text})
        return data["warnings"]


class OutputRowTest(Base):
    def test_every_key_of_an_output_row(self):
        data, _ = self.queue({"rehearse": note(
            status="parked", up="[[ERP Postgres 17 upgrade]]", priority="p1", due="2026-11-18",
            aliases="[Rehearse the clone]",
            next_lines=["- [ ] Restore last night's backup (~3 h)"])})
        self.assertEqual(data["format"], "task-queue/1")
        self.assertEqual(data["first_day"], "2026-11-16")
        self.assertEqual(data["until"], "2026-11-20")
        self.assertEqual(data["tasks"], [{
            "title": "rehearse: Restore last night's backup",
            "task": "rehearse", "name": "Rehearse the clone", "source": "vault",
            "hub": "ERP Postgres 17 upgrade", "status": "parked", "priority": "p1",
            "deadline": "2026-11-18", "minutes": 180}])
        self.assertEqual(data["not_placed"], [])
        self.assertEqual(data["warnings"], [])


class ValueReadingTest(Base):
    """One test per row of the "How a value is read" table."""

    def test_priority_absent_or_empty_reads_as_p3_without_warning(self):
        for pr in (None, ""):
            with self.subTest(priority=pr):
                data, _ = self.queue({"t": note(priority=pr)})
                self.assertEqual(data["tasks"][0]["priority"], "p3")
                self.assertEqual(data["warnings"], [])
                shutil.rmtree(self.tmp / "vaults")

    def test_priority_not_p0_to_p5_reads_as_p3_with_warning(self):
        for pr in ("P1", "high", "p6"):
            with self.subTest(priority=pr):
                data, _ = self.queue({"t": note(priority=pr)})
                self.assertEqual(data["tasks"][0]["priority"], "p3")
                self.assertEqual(data["warnings"], [
                    {"task": "t", "field": "priority", "value": pr,
                     "detail": "expected p0..p5, read as p3"}])
                shutil.rmtree(self.tmp / "vaults")

    def test_due_absent_or_empty_is_no_limit_without_warning(self):
        for due in (None, ""):
            with self.subTest(due=due):
                data, _ = self.queue({"t": note(due=due)})
                self.assertNotIn("deadline", data["tasks"][0])
                self.assertEqual(data["warnings"], [])
                shutil.rmtree(self.tmp / "vaults")

    def test_due_not_a_date_is_no_limit_with_warning(self):
        for due in ("tomorrow", "2026-13-01", "2026-11-1"):
            with self.subTest(due=due):
                data, _ = self.queue({"t": note(due=due)})
                self.assertNotIn("deadline", data["tasks"][0])
                self.assertEqual(data["warnings"], [
                    {"task": "t", "field": "due", "value": due,
                     "detail": "expected YYYY-MM-DD, read as no due date"}])
                shutil.rmtree(self.tmp / "vaults")

    def test_started_absent_empty_or_not_a_date_sorts_after_dated(self):
        data, _ = self.queue({"a-none": note(started=None), "b-empty": note(started=""),
                              "c-bad": note(started="soon"), "z-dated": note(started="2026-11-10")})
        self.assertEqual(data["tasks"][0]["task"], "z-dated")
        self.assertEqual([r["task"] for r in data["tasks"][1:]], ["a-none", "b-empty", "c-bad"])
        self.assertEqual(data["warnings"], [])


class NextStateTest(Base):
    """One test per row of the "State of ## Next" table."""

    def test_every_open_item_estimated_is_placed_with_the_sum(self):
        r = self.row(note(next_lines=["- [ ] One (~20 min)", "- [ ] Two (~1 h)"]))
        self.assertEqual(r["minutes"], 80)

    def test_an_item_without_estimate_is_needs_an_estimate(self):
        r = self.not_placed(note(next_lines=["- [ ] One (~20 min)", "- [ ] Two",
                                             "- [ ] Three", "- [ ] Four (~5 min)"]))
        self.assertEqual(r, {"task": "t", "name": "Heading", "reason": "needs an estimate",
                             "detail": "2 of 4 open Next items have no estimate"})

    def test_no_open_item_is_no_next_item(self):
        r = self.not_placed(note(next_lines=["- [x] Done (~5 min)", "- [ ] "]))
        self.assertEqual(r, {"task": "t", "name": "Heading", "reason": "no Next item",
                             "detail": "no open Next item under ## Next"})

    def test_no_next_section_is_no_next_item(self):
        r = self.not_placed(note(next_lines=None))
        self.assertEqual(r["reason"], "no Next item")
        self.assertEqual(r["detail"], "no open Next item under ## Next")


class NextReadingTest(Base):
    def test_nested_items_count(self):
        r = self.row(note(next_lines=["- [ ] Parent (~10 min)", "    - [ ] Child (~5 min)",
                                      "\t- [ ] Tab child (~5 min)"]))
        self.assertEqual(r["minutes"], 20)

    def test_ticked_lines_and_empty_placeholder_do_not_count(self):
        r = self.row(note(next_lines=["- [x] Done (~99 min)", "- [ ] ", "- [ ]   ",
                                      "- [ ] Real (~10 min)"]))
        self.assertEqual(r["minutes"], 10)
        self.assertEqual(r["title"], "t: Real")

    def test_section_ends_at_the_next_heading(self):
        r = self.row(note(next_lines=["- [ ] In (~10 min)"],
                          body_after="## Open loops\n- [ ] Not in (~50 min)\n"))
        self.assertEqual(r["minutes"], 10)


class EstimateTest(Base):
    def minutes(self, item):
        return self.row(note(next_lines=[f"- [ ] Item {item}"]))["minutes"]

    def test_minutes_with_a_space(self):
        self.assertEqual(self.minutes("(~30 min)"), 30)

    def test_minutes_without_a_space(self):
        self.assertEqual(self.minutes("(~30min)"), 30)

    def test_whole_hours(self):
        self.assertEqual(self.minutes("(~2 h)"), 120)

    def test_decimal_hours(self):
        self.assertEqual(self.minutes("(~1.5 h)"), 90)

    def test_space_after_tilde(self):
        self.assertEqual(self.minutes("(~ 15 min)"), 15)

    def test_rounding_up_per_item(self):
        # 0.02 h = 1.2 min: each item rounds up to 2, so two give 4 (not 3 from rounding the sum).
        r = self.row(note(next_lines=["- [ ] A (~0.02 h)", "- [ ] B (~0.02 h)"]))
        self.assertEqual(r["minutes"], 4)

    def test_estimate_must_end_the_line(self):
        r = self.not_placed(note(next_lines=["- [ ] Item (~30 min) then more"]))
        self.assertEqual(r["reason"], "needs an estimate")


class FrontmatterTest(Base):
    def test_quoted_scalars(self):
        r = self.row(note(status='"active"', priority="'p1'", due='"2026-11-18"'))
        self.assertEqual((r["status"], r["priority"], r["deadline"]), ("active", "p1", "2026-11-18"))

    def test_trailing_comment(self):
        r = self.row(note(priority="p2   # above normal", due="  # YYYY-MM-DD, or empty"))
        self.assertEqual(r["priority"], "p2")
        self.assertNotIn("deadline", r)

    def test_unquoted_value_drops_a_trailing_comment(self):
        self.assertEqual(self.row(note(priority="p1 # note"))["priority"], "p1")

    def test_quoted_alias_keeps_its_hash(self):
        self.assertEqual(self.row(note(aliases='"Fix #42 crash"'))["name"], "Fix #42 crash")

    def test_quoted_up_keeps_its_hash(self):
        self.assertEqual(self.row(note(up="[[Projects/Hub #2|x]]"))["hub"], "Hub #2")

    def test_quoted_value_then_a_comment(self):
        self.assertEqual(self.row(note(aliases='"Fix #42" # why'))["name"], "Fix #42")

    def test_aliases_inline_list(self):
        self.assertEqual(self.row(note(aliases="[First one, Second]"))["name"], "First one")

    def test_aliases_block_list(self):
        r = self.row(note(aliases="", extra_front="tags: [task]").replace(
            "aliases: \n", "aliases:\n  - Block alias\n  - Other\n"))
        self.assertEqual(r["name"], "Block alias")

    def test_up_with_an_alias(self):
        self.assertEqual(self.row(note(up="[[Some Hub|shown]]"))["hub"], "Some Hub")

    def test_up_with_a_folder(self):
        self.assertEqual(self.row(note(up="[[Projects/Deep/Some Hub]]"))["hub"], "Some Hub")

    def test_up_empty_link(self):
        self.assertEqual(self.row(note(up="[[]]"))["hub"], "")

    def test_up_absent(self):
        self.assertEqual(self.row(note(up=None))["hub"], "")


class UnreadableTest(Base):
    def test_not_utf8(self):
        r = self.not_placed(b"---\nstatus: done\n---\n\xff\xfe bad\n")
        self.assertEqual(r, {"task": "t", "name": "t", "reason": "unreadable note",
                             "detail": "not UTF-8"})

    def test_no_frontmatter(self):
        r = self.not_placed("# Just a heading\n\n## Next\n- [ ] Do (~5 min)\n")
        self.assertEqual(r, {"task": "t", "name": "t", "reason": "unreadable note",
                             "detail": "no frontmatter"})


class NameChainTest(Base):
    def test_alias_first(self):
        self.assertEqual(self.row(note(aliases="[Alias]", heading="Head"))["name"], "Alias")

    def test_heading_without_alias(self):
        self.assertEqual(self.row(note(heading="Head"))["name"], "Head")

    def test_slug_without_alias_or_heading(self):
        self.assertEqual(self.row(note(heading=""), slug="my-slug")["name"], "my-slug")


def task(key="v:t", priority="p3", due=None, started="2026-11-01"):
    return {"key": key, "priority": priority, "due": due, "started": started}


class OrderingRuleTest(unittest.TestCase):
    """sort_key(task, until): the pure ordering rule. UNTIL is the window's end."""
    UNTIL = "2026-11-20"

    def order(self, *tasks):
        return [t["key"] for t in sorted(tasks, key=lambda t: task_queue.sort_key(t, self.UNTIL))]

    def test_tier_0_p0_ahead_of_everything_dated(self):
        self.assertEqual(self.order(task("v:dated", "p1", due="2026-11-01"), task("v:zero", "p0")),
                         ["v:zero", "v:dated"])

    def test_tier_1_due_inside_window_ahead_of_undated(self):
        self.assertEqual(self.order(task("v:undated", "p1"), task("v:due", "p5", due="2026-11-20")),
                         ["v:due", "v:undated"])

    def test_tier_2_priority_decides(self):
        self.assertEqual(self.order(task("v:low", "p4"), task("v:high", "p1"), task("v:mid", "p3")),
                         ["v:high", "v:mid", "v:low"])

    def test_overdue_ahead_of_later_dates(self):
        self.assertEqual(self.order(task("v:later", "p1", due="2026-11-18"),
                                    task("v:overdue", "p5", due="2026-11-02")),
                         ["v:overdue", "v:later"])

    def test_due_after_until_does_not_affect_p1_to_p5(self):
        self.assertEqual(self.order(task("v:a-far", "p4", due="2026-11-21"), task("v:b-near", "p2")),
                         ["v:b-near", "v:a-far"])
        self.assertEqual(task_queue.sort_key(task("v:x", "p2", due="2026-12-31"), self.UNTIL),
                         task_queue.sort_key(task("v:x", "p2"), self.UNTIL))

    def test_dated_p0_ahead_of_undated_p0(self):
        self.assertEqual(self.order(task("v:a-undated", "p0"), task("v:z-dated", "p0", due="2027-03-01")),
                         ["v:z-dated", "v:a-undated"])

    def test_started_tie_break_older_first_undated_last(self):
        self.assertEqual(self.order(task("v:a", started=None), task("v:b", started="2026-11-05"),
                                    task("v:c", started="2026-10-01")),
                         ["v:c", "v:b", "v:a"])

    def test_vault_slug_tie_break(self):
        self.assertEqual(self.order(task("b:a"), task("a:z"), task("a:b")), ["a:b", "a:z", "b:a"])


class VaultsTest(Base):
    def test_done_notes_excluded(self):
        data, _ = self.queue({"done": note(status="done"), "open": note()})
        self.assertEqual([r["task"] for r in data["tasks"]], ["open"])
        self.assertEqual(data["not_placed"], [])

    def test_missing_or_misspelled_status_included(self):
        data, _ = self.queue({"a": note(status=None), "b": note(status="dnoe")})
        self.assertEqual([(r["task"], r["status"]) for r in data["tasks"]], [("a", ""), ("b", "dnoe")])

    def test_two_vaults_merged_into_one_order(self):
        a = self.vault("work", {"x": note(priority="p4"), "y": note(priority="p1")})
        b = self.vault("home", {"z": note(priority="p2"), "w": note(priority="p4")})
        r = self.run_tool("--vault", f"work={a}", "--vault", f"home={b}", "--week-start", WEEK)
        data = json.loads(self.wrote(r.stdout).read_text())
        self.assertEqual([t["task"] for t in data["tasks"]], ["work:y", "home:z", "home:w", "work:x"])
        self.assertEqual(data["tasks"][0]["title"], "work:y: Do it")

    def test_bare_slug_with_one_vault(self):
        self.assertEqual(self.row(note(), slug="s")["task"], "s")

    def test_one_row_per_task_titled_with_first_item(self):
        r = self.row(note(next_lines=["- [ ] First (~10 min)", "- [ ] Second (~20 min)",
                                      "- [ ] Third (~1 h)"]), slug="s")
        self.assertEqual((r["title"], r["minutes"]), ("s: First", 90))


class PeriodTest(Base):
    def first_until(self, *args):
        root = self.vault("v", {"t": note()})
        data = json.loads(self.wrote(self.run_tool("--vault", f"v={root}", *args).stdout).read_text())
        return data["first_day"], data["until"]

    def test_date_until_is_six_days_later(self):
        self.assertEqual(self.first_until("--date", "2026-11-18"), ("2026-11-18", "2026-11-24"))

    def test_week_start_matches_plan_days(self):
        _, days = planner_config.plan_days(dt.date.today(), dt.date.fromisoformat(WEEK), False)
        self.assertEqual(self.first_until("--week-start", WEEK), (days[0], days[-1]))
        self.assertEqual(days[-1], "2026-11-20")

    def test_no_flag_matches_plan_days_from_today(self):
        _, days = planner_config.plan_days(dt.date.today(), None, False)
        self.assertEqual(self.first_until(), (days[0], days[-1]))

    def test_include_weekend_extends_until_to_sunday(self):
        self.assertEqual(self.first_until("--week-start", WEEK, "--include-weekend"),
                         ("2026-11-16", "2026-11-22"))


class OutputFileTest(Base):
    def setUp(self):
        super().setUp()
        self.root = self.vault("v", {"t": note()})

    def test_no_out_creates_a_new_queue_run_file(self):
        r = self.run_tool("--vault", f"v={self.root}")
        path = self.wrote(r.stdout)
        self.assertEqual(path.parent.resolve(), self.out_dir.resolve())
        self.assertTrue(path.name.startswith("queue-run-") and path.name.endswith(".json"))
        self.assertEqual(json.loads(path.read_text())["format"], "task-queue/1")
        self.assertTrue(r.stdout.endswith(f"Wrote {path}\n"))

    def test_out_file_written_and_named_last(self):
        out = self.tmp / "mine.json"
        r = self.run_tool("--vault", f"v={self.root}", "--out", out)
        self.assertEqual(self.wrote(r.stdout), out)
        self.assertEqual(json.loads(out.read_text())["format"], "task-queue/1")

    def test_twenty_concurrent_runs_get_twenty_complete_files(self):
        cmd = [sys.executable, str(self.tools / "task_queue.py"), "--vault", f"v={self.root}"]
        procs = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for _ in range(20)]
        paths = []
        for p in procs:
            out, err = p.communicate()
            self.assertEqual(p.returncode, 0, err)
            paths.append(self.wrote(out))
        self.assertEqual(len(set(paths)), 20)
        for path in paths:
            self.assertEqual(len(json.loads(path.read_text())["tasks"]), 1)

    def test_old_queue_run_files_deleted_others_left(self):
        self.out_dir.mkdir()
        two_days = time.time() - 2 * 24 * 3600
        old, new = self.out_dir / "queue-run-old.json", self.out_dir / "queue-run-new.json"
        backup, other = self.out_dir / "queue-backup.json", self.out_dir / "plan-2026-11-16.md"
        for p in (old, new, backup, other):
            p.write_text("{}")
        for p in (old, backup, other):
            os.utime(p, (two_days, two_days))
        self.run_tool("--vault", f"v={self.root}")
        self.assertFalse(old.exists())
        self.assertTrue(new.exists() and backup.exists() and other.exists())

    def test_two_runs_on_the_same_input_are_identical(self):
        self.vault("v", {"a": note(priority="p1", due="2026-11-02"), "b": note(priority="bad"),
                         "c": note(next_lines=None)})
        p1 = self.wrote(self.run_tool("--vault", f"v={self.root}", "--week-start", WEEK).stdout)
        p2 = self.wrote(self.run_tool("--vault", f"v={self.root}", "--week-start", WEEK).stdout)
        self.assertNotEqual(p1, p2)
        self.assertEqual(p1.read_bytes(), p2.read_bytes())


class OverdueTest(Base):
    def test_overdue_set_before_first_day_absent_from_first_day_on(self):
        data, out = self.queue({"late": note(due="2026-11-15"), "today": note(due="2026-11-16"),
                                "later": note(due="2026-11-19")})
        rows = {r["task"]: r for r in data["tasks"]}
        self.assertIs(rows["late"]["overdue"], True)
        self.assertNotIn("overdue", rows["today"])
        self.assertNotIn("overdue", rows["later"])
        self.assertIn("p3 2026-11-15 (overdue) 30m late: Do it", out.splitlines())
        self.assertIn("p3 2026-11-16 30m today: Do it", out.splitlines())


class SortedListsTest(Base):
    def test_not_placed_and_warnings_sorted_by_task(self):
        data, _ = self.queue({"c": note(next_lines=None, priority="x"), "a": note(next_lines=None, due="no"),
                              "b": b"\xff", "d": note(priority="high")})
        self.assertEqual([r["task"] for r in data["not_placed"]], ["a", "b", "c"])
        self.assertEqual([w["task"] for w in data["warnings"]], ["a", "c", "d"])


class ExitCodeTest(Base):
    def test_duplicate_vault_name(self):
        a = self.vault("a")
        r = self.run_tool("--vault", f"x={a}", "--vault", f"x={a}", expect=2)
        self.assertIn("'x'", r.stderr)

    def test_missing_path(self):
        r = self.run_tool("--vault", f"x={self.tmp / 'nope'}", expect=2)
        self.assertIn("nope", r.stderr)

    def test_folder_without_tasks(self):
        (self.tmp / "empty").mkdir()
        r = self.run_tool("--vault", f"x={self.tmp / 'empty'}", expect=2)
        self.assertIn("Tasks/", r.stderr)

    def test_no_vault_is_an_error(self):
        self.run_tool(expect=2)

    def test_every_task_not_placed_exits_0(self):
        data, out = self.queue({"a": note(next_lines=None), "b": note(next_lines=["- [ ] x"])})
        self.assertEqual(data["tasks"], [])
        self.assertEqual(len(data["not_placed"]), 2)


class SummaryTest(Base):
    def test_text_summary(self):
        a = self.vault("vail", {"handoff-runbook": note(priority="p2", due="2026-11-10",
                                                        next_lines=["- [ ] Review the runbook draft (~45 min)"]),
                                "some-task": note(next_lines=["- [ ] a (~1 min)", "- [ ] b", "- [ ] c",
                                                              "- [ ] d (~1 min)"])})
        b = self.vault("arryved", {"erp-pg17-rehearse": note(priority="p1", due="2026-11-18",
                                                             next_lines=["- [ ] Restore last night's backup (~3 h)"])})
        c = self.vault("personal", {"renew-domain": note(next_lines=["- [ ] Log in to the registrar (~25 min)"]),
                                    "other-task": note(priority="high", next_lines=None)})
        r = self.run_tool("--vault", f"vail={a}", "--vault", f"arryved={b}", "--vault", f"personal={c}",
                          "--week-start", WEEK)
        path = self.wrote(r.stdout)
        self.assertEqual(r.stdout, "\n".join([
            "p2 2026-11-10 (overdue) 45m vail:handoff-runbook: Review the runbook draft",
            "p1 2026-11-18 180m arryved:erp-pg17-rehearse: Restore last night's backup",
            "p3 - 25m personal:renew-domain: Log in to the registrar",
            "",
            "Not placed (needs an estimate):",
            "- vail:some-task: 2 of 4 open Next items have no estimate",
            "",
            "Not placed (no Next item):",
            "- personal:other-task: no open Next item under ## Next",
            "",
            "Warnings:",
            '- personal:other-task: priority "high": expected p0..p5, read as p3',
            "",
            f"Wrote {path}",
        ]) + "\n")


if __name__ == "__main__":
    unittest.main()
