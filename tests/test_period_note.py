"""Tests for tools/period_note.py. Run: python3 -m unittest tests.test_period_note

Most tests call period_note.main(argv, today=…) in-process on temporary vault
folders, or the pure functions directly. One subprocess test runs the
`__main__` guard.
"""
import contextlib
import datetime as dt
import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "planner" / "tools"
sys.path.insert(0, str(TOOLS))
import period_note  # noqa: E402

D = dt.date


class RecurrenceListTest(unittest.TestCase):
    def test_weekday_rule_parses(self):
        rules, warnings = period_note.parse_recurring(
            "- [ ] Weekly review (~30 min) — every: mon #id/weekly-review\n")
        self.assertEqual(warnings, [])
        occs = period_note.occurrences(rules, "week", "2026-W48")
        self.assertEqual(occs, [period_note.Occurrence(
            "weekly-review-2026-w48", "Weekly review (~30 min)", D(2026, 11, 23))])

    def dates(self, line, kind, period):
        rules, warnings = period_note.parse_recurring(line + "\n")
        self.assertEqual(warnings, [])
        return [o.date for o in period_note.occurrences(rules, kind, period)]

    def test_every_weekday_falls_in_its_week(self):
        for i, day in enumerate(["mon", "tue", "wed", "thu", "fri", "sat", "sun"]):
            self.assertEqual(self.dates(f"- [ ] X — every: {day} #id/x", "week", "2026-W53"),
                             [D(2026, 12, 28) + dt.timedelta(days=i)])

    def test_month_n(self):
        self.assertEqual(self.dates("- [ ] Rent — every: month 1 #id/rent", "month", "2026-11"),
                         [D(2026, 11, 1)])

    def test_month_31_in_november_falls_on_nov_30(self):
        self.assertEqual(self.dates("- [ ] X — every: month 31 #id/x", "month", "2026-11"),
                         [D(2026, 11, 30)])

    def test_month_last(self):
        self.assertEqual(self.dates("- [ ] X — every: month last #id/x", "month", "2028-02"),
                         [D(2028, 2, 29)])

    def test_month_first_weekday(self):
        self.assertEqual(self.dates("- [ ] X — every: month first-tue #id/x", "month", "2026-12"),
                         [D(2026, 12, 1)])
        self.assertEqual(self.dates("- [ ] X — every: month first-mon #id/x", "month", "2026-12"),
                         [D(2026, 12, 7)])

    def test_weekly_rules_stay_out_of_months_and_monthly_out_of_weeks(self):
        rules, _ = period_note.parse_recurring(
            "- [ ] W — every: mon #id/w\n- [ ] M — every: month 1 #id/m\n")
        self.assertEqual([o.id for o in period_note.occurrences(rules, "week", "2026-W48")],
                         ["w-2026-w48"])
        self.assertEqual([o.id for o in period_note.occurrences(rules, "month", "2026-11")],
                         ["m-2026-11"])

    def test_ticked_line_is_read(self):
        self.assertEqual(self.dates("- [x] X — every: fri #id/x", "week", "2026-W48"),
                         [D(2026, 11, 27)])

    def test_lines_in_fenced_code_blocks_are_ignored(self):
        text = ("# Recurring\n```\n- [ ] A — every: mon #id/a\n- [ ] bad every: zzz\n```\n"
                "~~~\n- [ ] B — every: tue #id/b\n~~~\n- [ ] C — every: wed #id/c\n")
        rules, warnings = period_note.parse_recurring(text)
        self.assertEqual(warnings, [])
        self.assertEqual([r.id for r in rules], ["c"])

    def test_other_text_is_ignored(self):
        rules, warnings = period_note.parse_recurring(
            "# Work\n\nSome notes.\n- [ ] not a rule\n- [ ] A — every: mon #id/a\n")
        self.assertEqual((len(rules), warnings), (1, []))

    def test_each_bad_line_reason_names_its_line(self):
        text = ("# List\n"
                "- [ ] A — every: biweekly #id/a\n"
                "- [ ] B — every: month 32 #id/b\n"
                "- [ ] C — every: month 0 #id/c\n"
                "- [ ] D — every: mon\n"
                "Pay rent every: month\n"
                "- [ ] E — every: Mon #id/e\n"
                "- [ ] F — every: tue #id/f\n")
        rules, warnings = period_note.parse_recurring(text)
        self.assertEqual([r.id for r in rules], ["f"])
        self.assertEqual(warnings, [
            "Recurring.md:2: unknown rule 'biweekly'",
            "Recurring.md:3: month 32 out of range 1–31",
            "Recurring.md:4: month 0 out of range 1–31",
            "Recurring.md:5: missing #id/",
            "Recurring.md:6: does not match the line format",
            "Recurring.md:7: unknown rule 'Mon'",
        ])

    def test_three_lines_sharing_an_id_give_one_warning_and_are_all_skipped(self):
        text = ("- [ ] A — every: mon #id/dup\n- [ ] Keep — every: tue #id/keep\n"
                "- [ ] B — every: month 1 #id/dup\n\n- [ ] C — every: fri #id/dup\n")
        rules, warnings = period_note.parse_recurring(text)
        self.assertEqual([r.id for r in rules], ["keep"])
        self.assertEqual(warnings, ["Recurring.md: id 'dup' on lines 1, 3, 5; all skipped"])


W48_NOTE = """---
period: 2026-W48
month: "[[2026-11]]"
added: [weekly-review-2026-w48]
tags: [weekly]
---
# Week 48 · Nov 23 – Nov 29, 2026

Months: [[2026-11]]

## Plan
<!-- planner:plan-week:start -->
<!-- planner:plan-week:end -->

## Recurring
<!-- planner:recurring:start -->
- [ ] Weekly review (~30 min) — 2026-11-23 ^weekly-review-2026-w48
<!-- planner:recurring:end -->

## Notes
"""

NOV_NOTE = """---
period: 2026-11
added: [close-books-2026-11]
tags: [monthly]
---
# November 2026

## Recurring
<!-- planner:recurring:start -->
- [ ] Close books — 2026-11-30 ^close-books-2026-11
<!-- planner:recurring:end -->

## Notes
"""


class NewNoteTest(unittest.TestCase):
    def test_week_titles(self):
        self.assertEqual(period_note.title_week(D(2026, 11, 23)), "Week 48 · Nov 23 – Nov 29, 2026")
        self.assertEqual(period_note.title_week(D(2026, 11, 30)), "Week 49 · Nov 30 – Dec 6, 2026")
        self.assertEqual(period_note.title_week(D(2026, 12, 28)), "Week 53 · Dec 28, 2026 – Jan 3, 2027")
        self.assertEqual(period_note.title_week(D(2027, 1, 4)), "Week 1 · Jan 4 – Jan 10, 2027")

    def test_month_title(self):
        self.assertEqual(period_note.title_month("2026-11"), "November 2026")
        self.assertEqual(period_note.title_month("2027-01"), "January 2027")

    def test_new_week_note_matches_the_spec_bytes(self):
        occ = period_note.Occurrence("weekly-review-2026-w48", "Weekly review (~30 min)", D(2026, 11, 23))
        self.assertEqual(period_note.new_week_note(D(2026, 11, 23), [occ]), W48_NOTE)

    def test_new_month_note_matches_the_spec_bytes(self):
        occ = period_note.Occurrence("close-books-2026-11", "Close books", D(2026, 11, 30))
        self.assertEqual(period_note.new_month_note("2026-11", [occ]), NOV_NOTE)

    def test_empty_notes_have_an_empty_ledger_and_empty_markers(self):
        week = period_note.new_week_note(D(2026, 11, 30), [])
        self.assertIn('month: "[[2026-12]]"\nadded: []\n', week)
        self.assertIn("Months: [[2026-11]] · [[2026-12]]\n", week)
        self.assertIn("<!-- planner:recurring:start -->\n<!-- planner:recurring:end -->\n", week)
        self.assertEqual(period_note.new_month_note("2026-12", []), (
            "---\nperiod: 2026-12\nadded: []\ntags: [monthly]\n---\n# December 2026\n\n"
            "## Recurring\n<!-- planner:recurring:start -->\n<!-- planner:recurring:end -->\n\n"
            "## Notes\n"))

    def test_two_occurrences_are_listed_in_order(self):
        occs = [period_note.Occurrence("a-2026-w48", "A", D(2026, 11, 23)),
                period_note.Occurrence("b-2026-w48", "B", D(2026, 11, 27))]
        week = period_note.new_week_note(D(2026, 11, 23), occs)
        self.assertIn("added: [a-2026-w48, b-2026-w48]\n", week)
        self.assertIn("- [ ] A — 2026-11-23 ^a-2026-w48\n- [ ] B — 2026-11-27 ^b-2026-w48\n", week)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def vault(self, name, recurring=None):
        root = self.tmp / name
        root.mkdir()
        if recurring is not None:
            data = recurring if isinstance(recurring, bytes) else recurring.encode("utf-8")
            (root / "Recurring.md").write_bytes(data)
        return root

    def run_main(self, *argv, today=D(2026, 11, 22), expect=0):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = period_note.main(list(map(str, argv)), today=today)
        self.assertEqual(code, expect, out.getvalue() + err.getvalue())
        return out.getvalue().splitlines()

    def run_fail(self, *argv, today=D(2026, 11, 22)):
        """Run expecting exit 2; returns stderr."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                self.assertRaises(SystemExit) as cm:
            period_note.main(list(map(str, argv)), today=today)
        self.assertEqual(cm.exception.code, 2, out.getvalue() + err.getvalue())
        return err.getvalue()


class CujTest(Base):
    def test_cuj1_sunday_planning_creates_month_then_week(self):
        arryved = self.vault("arryved", "# Recurring\n\n"
                             "- [ ] Weekly review (~30 min) — every: mon #id/weekly-review\n"
                             "- [ ] Close books — every: month last #id/close-books\n")
        personal = self.vault("personal")
        lines = self.run_main("ensure", "--plan-week",
                              "--vault", f"arryved={arryved}", "--vault", f"personal={personal}")
        self.assertEqual(lines, [
            "Week 2026-W48 (Monday 2026-11-23)",
            "Wrote arryved:Monthly/2026-11.md",
            "Wrote arryved:Weekly/2026-W48.md",
            "Off personal: no Recurring.md",
        ])
        self.assertEqual((arryved / "Weekly" / "2026-W48.md").read_bytes(), W48_NOTE.encode())
        self.assertEqual((arryved / "Monthly" / "2026-11.md").read_bytes(), NOV_NOTE.encode())
        self.assertEqual(sorted(os.listdir(personal)), [])

    def test_cuj3_monthly_item_in_a_week_of_the_other_month(self):
        arryved = self.vault("arryved", "- [ ] Weekly review — every: mon #id/weekly-review\n"
                             "- [ ] Close books — every: month last #id/close-books\n"
                             "- [ ] Rent — every: month 1 #id/rent\n")
        self.run_main("ensure", "--plan-week", "--vault", f"arryved={arryved}")  # CUJ 1, W48
        nov = (arryved / "Monthly" / "2026-11.md")
        nov_before = nov.read_bytes()
        self.assertIn(b"- [ ] Close books \xe2\x80\x94 2026-11-30 ^close-books-2026-11\n", nov_before)
        lines = self.run_main("ensure", "--plan-week", "--vault", f"arryved={arryved}",
                              today=D(2026, 11, 28))
        self.assertEqual(lines, [
            "Week 2026-W49 (Monday 2026-11-30)",
            "Unchanged arryved:Monthly/2026-11.md",
            "Wrote arryved:Monthly/2026-12.md",
            "Wrote arryved:Weekly/2026-W49.md",
        ])
        self.assertEqual(nov.read_bytes(), nov_before)
        dec = (arryved / "Monthly" / "2026-12.md").read_text(encoding="utf-8")
        self.assertIn("added: [close-books-2026-12, rent-2026-12]\n", dec)
        self.assertIn("- [ ] Rent — 2026-12-01 ^rent-2026-12\n", dec)
        week = (arryved / "Weekly" / "2026-W49.md").read_text(encoding="utf-8")
        self.assertIn('month: "[[2026-12]]"\n', week)
        self.assertIn("\nMonths: [[2026-11]] · [[2026-12]]\n", week)
        self.assertIn("# Week 49 · Nov 30 – Dec 6, 2026\n", week)
        self.assertNotIn("Close books", week)
        self.assertNotIn("Rent", week)
        self.assertIn("added: [weekly-review-2026-w49]\n", week)

    def test_cuj4_skipped_week_gets_its_notes(self):
        arryved = self.vault("arryved", "- [ ] Weekly review — every: mon #id/weekly-review\n"
                             "- [ ] Retro — every: fri #id/retro\n")
        (arryved / "Monthly").mkdir()
        (arryved / "Monthly" / "2026-12.md").write_bytes(b"---\nperiod: 2026-12\n---\nmine\n")
        lines = self.run_main("ensure", "--date", "2026-12-07", "--vault", f"arryved={arryved}",
                              today=D(2026, 12, 7))
        self.assertEqual(lines, [
            "Week 2026-W50 (Monday 2026-12-07)",
            "Unchanged arryved:Monthly/2026-12.md",
            "Wrote arryved:Weekly/2026-W50.md",
        ])
        week = (arryved / "Weekly" / "2026-W50.md").read_text(encoding="utf-8")
        self.assertIn("<!-- planner:plan-week:start -->\n<!-- planner:plan-week:end -->\n", week)
        self.assertIn("- [ ] Weekly review — 2026-12-07 ^weekly-review-2026-w50\n"
                      "- [ ] Retro — 2026-12-11 ^retro-2026-w50\n", week)
        self.assertEqual((arryved / "Monthly" / "2026-12.md").read_bytes(),
                         b"---\nperiod: 2026-12\n---\nmine\n")


class EnsureTest(Base):
    REC = "- [ ] Review — every: mon #id/review\n"

    def test_w53_spans_two_years(self):
        v = self.vault("v", self.REC)
        lines = self.run_main("ensure", "--date", "2027-01-03", "--vault", f"v={v}")
        self.assertEqual(lines, ["Week 2026-W53 (Monday 2026-12-28)", "Wrote v:Monthly/2026-12.md",
                                 "Wrote v:Monthly/2027-01.md", "Wrote v:Weekly/2026-W53.md"])
        week = (v / "Weekly" / "2026-W53.md").read_text(encoding="utf-8")
        self.assertIn("period: 2026-W53\nmonth: \"[[2026-12]]\"\n", week)
        self.assertIn("# Week 53 · Dec 28, 2026 – Jan 3, 2027\n", week)
        self.assertIn("Months: [[2026-12]] · [[2027-01]]\n", week)

    def test_repeat_run_is_unchanged_and_keeps_mtime(self):
        v = self.vault("v", self.REC)
        self.run_main("ensure", "--date", "2026-11-25", "--vault", f"v={v}")
        files = [v / "Weekly" / "2026-W48.md", v / "Monthly" / "2026-11.md"]
        old = [(f.read_bytes(), os.stat(f).st_mtime_ns) for f in files]
        for f in files:  # push mtimes into the past so a rewrite would show
            os.utime(f, ns=(1_000_000_000, 1_000_000_000))
        lines = self.run_main("ensure", "--date", "2026-11-25", "--vault", f"v={v}")
        self.assertEqual(lines[1:], ["Unchanged v:Monthly/2026-11.md", "Unchanged v:Weekly/2026-W48.md"])
        self.assertEqual([f.read_bytes() for f in files], [b for b, _ in old])
        self.assertEqual([os.stat(f).st_mtime_ns for f in files], [1_000_000_000] * 2)

    def test_existing_note_is_never_rewritten(self):
        v = self.vault("v", self.REC)
        (v / "Weekly").mkdir()
        mine = b"---\r\nperiod: 2026-W48\r\n---\r\n# my week\r\n"
        (v / "Weekly" / "2026-W48.md").write_bytes(mine)
        lines = self.run_main("ensure", "--date", "2026-11-23", "--vault", f"v={v}")
        self.assertEqual(lines[-1], "Unchanged v:Weekly/2026-W48.md")
        self.assertEqual((v / "Weekly" / "2026-W48.md").read_bytes(), mine)

    def test_off_vault_creates_nothing_and_exits_0(self):
        v = self.vault("v")
        lines = self.run_main("ensure", "--date", "2026-11-23", "--vault", f"v={v}")
        self.assertEqual(lines, ["Week 2026-W48 (Monday 2026-11-23)", "Off v: no Recurring.md"])
        self.assertEqual(os.listdir(v), [])

    def test_warnings_print_with_the_vault_name(self):
        v = self.vault("v", self.REC + "- [ ] X — every: daily #id/x\n")
        lines = self.run_main("ensure", "--date", "2026-11-23", "--vault", f"v={v}")
        self.assertEqual(lines[1], "Warning v:Recurring.md:2: unknown rule 'daily'")

    def test_recurring_not_utf8_writes_nothing_to_that_vault(self):
        bad = self.vault("bad", b"- [ ] Caf\xe9 \xe2\x80\x94 every: mon #id/x\n")
        good = self.vault("good", self.REC)
        lines = self.run_main("ensure", "--date", "2026-11-23", "--vault", f"bad={bad}",
                              "--vault", f"good={good}", expect=1)
        self.assertEqual(lines[1:], ["Skipped bad:Recurring.md: not UTF-8",
                                     "Wrote good:Monthly/2026-11.md", "Wrote good:Weekly/2026-W48.md"])
        self.assertEqual(os.listdir(bad), ["Recurring.md"])

    def test_existing_note_not_utf8_is_skipped_and_the_rest_goes_on(self):
        v = self.vault("v", self.REC)
        (v / "Monthly").mkdir()
        (v / "Monthly" / "2026-11.md").write_bytes(b"\xff\xfe")
        lines = self.run_main("ensure", "--date", "2026-11-23", "--vault", f"v={v}", expect=1)
        self.assertEqual(lines[1:], ["Skipped v:Monthly/2026-11.md: not UTF-8",
                                     "Wrote v:Weekly/2026-W48.md"])

    def test_weekly_as_a_file_is_skipped_with_the_os_error(self):
        v = self.vault("v", self.REC)
        (v / "Weekly").write_text("not a folder")
        lines = self.run_main("ensure", "--date", "2026-11-23", "--vault", f"v={v}", expect=1)
        self.assertEqual(lines[1], "Wrote v:Monthly/2026-11.md")
        self.assertRegex(lines[2], r"^Skipped v:Weekly/2026-W48\.md: (File exists|Not a directory)$")

    def test_monthly_as_a_file_skips_the_new_week_note(self):
        v = self.vault("v", self.REC)
        (v / "Monthly").write_text("not a folder")
        lines = self.run_main("ensure", "--date", "2026-11-23", "--vault", f"v={v}", expect=1)
        self.assertRegex(lines[1], r"^Skipped v:Monthly/2026-11\.md: (File exists|Not a directory)$")
        self.assertEqual(lines[2], "Skipped v:Weekly/2026-W48.md: month note Monthly/2026-11.md missing")
        self.assertFalse((v / "Weekly").exists())

    def test_no_temp_files_are_left(self):
        v = self.vault("v", self.REC)
        self.run_main("ensure", "--date", "2026-11-23", "--vault", f"v={v}")
        self.assertEqual(os.listdir(v / "Weekly"), ["2026-W48.md"])
        self.assertEqual(os.listdir(v / "Monthly"), ["2026-11.md"])


class DatesTest(Base):
    def setUp(self):
        super().setUp()
        self.v = self.vault("v")

    def first(self, *argv, today=D(2026, 11, 22)):
        return self.run_main("ensure", *argv, "--vault", f"v={self.v}", today=today)[0]

    def test_plan_week_on_sunday_picks_next_week(self):
        self.assertEqual(self.first("--plan-week"), "Week 2026-W48 (Monday 2026-11-23)")

    def test_plan_week_midweek_picks_this_week(self):
        self.assertEqual(self.first("--plan-week", today=D(2026, 11, 25)),
                         "Week 2026-W48 (Monday 2026-11-23)")

    def test_plan_week_with_week_start(self):
        self.assertEqual(self.first("--plan-week", "--week-start", "2026-12-28"),
                         "Week 2026-W53 (Monday 2026-12-28)")

    def test_date_picks_its_week(self):
        self.assertEqual(self.first("--date", "2026-12-07"), "Week 2026-W50 (Monday 2026-12-07)")
        self.assertEqual(self.first("--date", "2026-12-13"), "Week 2026-W50 (Monday 2026-12-07)")


class ArgumentsTest(Base):
    def setUp(self):
        super().setUp()
        self.v = self.vault("v")
        self.ok = f"v={self.v}"

    def test_no_vault(self):
        self.assertIn("--vault", self.run_fail("ensure", "--date", "2026-11-23"))

    def test_malformed_vault(self):
        self.assertIn("'novalue'", self.run_fail("ensure", "--date", "2026-11-23", "--vault", "novalue"))

    def test_vault_name_twice(self):
        err = self.run_fail("ensure", "--date", "2026-11-23", "--vault", self.ok, "--vault", self.ok)
        self.assertIn("'v' given twice", err)

    def test_vault_path_not_a_folder(self):
        err = self.run_fail("ensure", "--date", "2026-11-23", "--vault", f"x={self.tmp / 'nope'}")
        self.assertIn("nope", err)
        self.assertIn("is not a folder", err)

    def test_bad_date(self):
        self.assertIn("'2026-13-01'", self.run_fail("ensure", "--date", "2026-13-01", "--vault", self.ok))
        self.assertIn("'tomorrow'", self.run_fail("ensure", "--date", "tomorrow", "--vault", self.ok))

    def test_bad_week_start_date(self):
        err = self.run_fail("ensure", "--plan-week", "--week-start", "23/11/2026", "--vault", self.ok)
        self.assertIn("'23/11/2026'", err)

    def test_both_date_and_plan_week(self):
        err = self.run_fail("ensure", "--date", "2026-11-23", "--plan-week", "--vault", self.ok)
        self.assertIn("both", err)

    def test_neither_date_nor_plan_week(self):
        self.assertIn("neither", self.run_fail("ensure", "--vault", self.ok))

    def test_week_start_without_plan_week(self):
        err = self.run_fail("ensure", "--date", "2026-11-23", "--week-start", "2026-11-23", "--vault", self.ok)
        self.assertIn("--week-start 2026-11-23 needs --plan-week", err)

    def test_week_start_not_a_monday(self):
        err = self.run_fail("ensure", "--plan-week", "--week-start", "2026-11-25", "--vault", self.ok)
        self.assertIn("--week-start 2026-11-25 is not a Monday", err)

    def test_nothing_is_written_on_bad_arguments(self):
        v = self.vault("w", "- [ ] R — every: mon #id/r\n")
        self.run_fail("ensure", "--plan-week", "--week-start", "2026-11-25", "--vault", f"w={v}")
        self.assertEqual(os.listdir(v), ["Recurring.md"])


class MainGuardTest(Base):
    def test_runs_as_a_script(self):
        tools = self.tmp / "tools"
        tools.mkdir()
        for f in ("period_note.py", "planner_config.py"):
            shutil.copy(TOOLS / f, tools / f)
        v = self.vault("v")
        r = subprocess.run([sys.executable, str(tools / "period_note.py"), "ensure",
                            "--date", "2026-11-23", "--vault", f"v={v}"],
                           capture_output=True, text=True, cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "Week 2026-W48 (Monday 2026-11-23)\nOff v: no Recurring.md\n")
        r = subprocess.run([sys.executable, str(tools / "period_note.py"), "ensure", "--vault", f"v={v}"],
                           capture_output=True, text=True, cwd=self.tmp)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertTrue(r.stderr.startswith("ERROR: "), r.stderr)


if __name__ == "__main__":
    unittest.main()
