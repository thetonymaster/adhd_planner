# Implementation Readiness (Stage 9): `docs/designs/week-month-notes.md`, lines 575–879

**Reviewers:** egm-implementation-readiness, egm-codebase-details and egm-style, each in a fresh context. **Standard:** implementation-readiness-standard.

| Reviewer | Verdict |
|---|---|
| Implementation readiness | Not ready: 0 Blockers, 13 Majors, 10 Nits |
| Codebase details | Not ready: 0 Blockers, 13 Majors, 8 Nits |
| Style | Revise: 0 Blockers, 5 Majors, about 25 Nits |

**Combined verdict: not ready yet.** There are no Blockers, and every target file exists and accepts the change described. But:
- as written, two existing test files go red;
- several entries leave choices to the implementer that change bytes on disk or exit codes.

Most fixes are one or two sentences each.

In the tables below, **Verified** means the main session checked the claim against the code.

## Consolidated findings, deduplicated and ranked

### 🟡 R1. Existing tests would fail

| What | Evidence | Fix |
|---|---|---|
| The new `update-vaults` prompt changes the exact prompt lists | **Verified.** `setup/tests/test_actions.py:440` and `:609` assert `asked == [DOWNLOAD_Q…]` | Entry 15: update both tests. Either filter `asked` on download questions, as `hub_questions` does at `:684-685`, or expect the Recurring question first. |
| Rewording the plan-week stale-tools sentence | **Verified.** `tests/test_skill_files.py:51-55` asserts the exact sentence | Keep that sentence word for word, and add a separate `period_note.py` sentence with exact text. |

### 🟡 R2. Missed files and lines

| Where | Evidence | Fix |
|---|---|---|
| Setup skill "eleven" count | **Verified.** There are 3 places, not 2: `setup/SKILL.md:52` ("Eleven scripts…"), `:63` and `:66` | Change all three. Add `period_note.py` to the parenthetical at `:63`. The test asserts that "eleven" does not appear, ignoring case. |
| `tools/EGM.md` Invariants | **Verified.** The text to change is `:76`, "`task_queue.py` is the one tool that reads a vault". Entry 4 quotes text that doesn't exist. | Give the new sentence. Add a `period_note.py` invariant covering what it writes, atomicity and exit codes. |
| `tools/README.md` | `:31` says "the one script that reads a vault"; the script table at `:6-17` has no row for the new tool | Rewrite `:31` and add the row. |
| Setup's EGM docs | `setup/src/planner_setup/EGM.md:86,111`, `setup/EGM.md:11-13,26`, `setup/src/EGM.md:11` | Add entry 14a: list the new question, `Recurring.md` among the vault writes, and version 0.2.0. |
| `plugins/planner/EGM.md` | `:26,28` list each skill's tools; `:58-61` hold the stale-tools invariant | Extend entry 9. |

### 🟡 R3. Skill command form and flags

| What | Fix |
|---|---|
| The morning-startup bullet has no `cd "<planner-path>" &&`, no quoted `--vault`, and uses `<today>` | Use `cd "<planner-path>" && python3 tools/period_note.py ensure --date <Now: date> --vault "<name>=<vault-path>"` and put it in the "In this skill" list. |
| plan-week passes "the same period flags" to every tool, including `--include-weekend` (**verified**, `plan-week/SKILL.md:151-152`). `ensure` has no such flag, so argparse exits 2. | Reword the sentence: the same `--week-start` goes to all three tools, and `--include-weekend` goes only to `task_queue.py` and `plan_week.py`. |
| `test_skill_files.py:38-39` forbids `--week-start <YYYY-MM-DD>` in plan-week | Note this in entry 6. |

### 🟡 R4. Plan-section transform from `plan_week.py`'s output

The output of `plan_week.py` (`plan_week.py:140-169`) has these features, and the design doesn't say what to do with any of them:
- rows written as `- [ ] {title} — {N}m · pN (due D) (overdue)`;
- `## Mon Nov 23` headers;
- `_Meetings…_` and `_Free…_` lines;
- `- (open — no tasks assigned)` for empty days;
- a `_Planned…_` footer.

**Fix:** give the exact transform:
- `##` day headers become `###`;
- keep only the `- [ ]` rows, drop the `- [ ] ` prefix and the vault label, and keep the rest of the row as written;
- drop lines that start with `_` and the `- (open` placeholder.

Also correct the §3 example, which shows `90 min` where the tool writes `90m`.

### 🟡 R5. Checking the week label is ISO arithmetic done in prose

`ensure` prints `Weekly/2026-W48.md`, and the plan file is named after the Monday's date.

**Fix:** `ensure` prints a first line, `Week 2026-W48 (Monday 2026-11-23)`. The skill then compares two dates. Add this to the §4 table and add a test.

### 🟡 R6. No clock seam for testing `--plan-week`

A subprocess can't fake "Sunday". The `--week-start` path also bypasses the weekend rule.

**Fix:** use `main(argv, today=None)`, where only the `__main__` guard reads `dt.date.today()`. Test it in-process with `today=date(2026,11,22)` and expect W48.

### 🟡 R7. Reuse the atomic write instead of re-implementing it

`triage.write_atomic` (**verified**, `triage.py:79-91`) already handles three details the design leaves open:
- it uses a dot-prefixed temp name;
- it keeps the target file's mode, because `mkstemp` would otherwise leave 0600;
- it removes the temp file on error.

**Fix:** move `write_atomic` into `planner_config.py`, add a `prefix` parameter and write bytes, then import it from both tools. Alternatively, specify the port exactly.

### 🟡 R8. Argument validation is incomplete

The repo already has `task_queue.parse_vaults`, `parse_day` and `iso_date` (`task_queue.py:54-61, 274-294`).

**Fix:** move them, minus the `Tasks/` check, into `planner_config.py` and use them from both tools. List every exit-2 case and its message:
- `--vault` given twice;
- a path that isn't a folder;
- an invalid date;
- `--week-start` without `--plan-week`;
- a `--week-start` that isn't a Monday. Exit 2 here, because the skill already says "Pass `--week-start <Monday>`".

### 🟡 R9. Byte-level choices left open

- **Line endings of inserted lines:** new occurrence lines and a new `added:` line take the line ending of the frontmatter's first line. The precedent is `actions.py:247`.
- **New note with no occurrences:** give its exact bytes. Is it `added: []`? Is the Recurring section left empty?
- **Empty or scalar `added:`:** say whether `added:`, `added: foo` or quoted IDs count as empty, as missing (with a warning), or get unquoted.
- **Fence rules:** do ``` and `~~~` fences at column 0 both count, and does a `^ID` inside a fence count?
- **Warning texts:** give the `<reason>` text for bad rules (an unknown rule, `month 0`, `month 32`, a missing `#id/`), for three or more duplicates, and for ledger row 2.
- **Declining the `update-vaults` question:** give the exact line printed. Follow the `ctx.say` tense pattern: the imperative before the question, the past tense after it.

### 🟡 R10. Unreadable files and OS errors

Without a rule, a traceback in the middle of the loop breaks "other notes and vaults are still processed".

**Fix:**
- A file that isn't UTF-8 prints `Skipped <vault>:<path>: not UTF-8`. The precedent is `actions.py:229-235`.
- An `OSError` prints `Skipped <vault>:<path>: <strerror>`.
- A `Recurring.md` that isn't UTF-8 means that vault is not written at all.

Add one test for each case.

### 🟡 R11. The obsidian-vault rules conflict with period notes

The obsidian-vault rules say "Every note links up once via `up:`", and the verify step expects `deadends=Inbox only`. Period notes have no `up:` link, so they would be flagged.

**Fix:** entry 11 states the exception. Period notes and `Recurring.md` have no `up:`, and the expected dead ends become `Inbox`, `Monthly/*` and `Recurring.md`.

### 🟡 R12. `uv.lock` and the `--locked` check

CI runs `uv run --locked pytest`, and the lock pins `planner-setup` at 0.1.0.

**Fix:**
- In entry 22, run `cd setup && uv lock` and commit the result.
- In the verification steps, use `uv run --locked pytest`.

### 🟡 R13. No phases

**Fix:** group the entries into five phases. Each phase ends with its check command:

1. Library and tool: entries 1, 16, 2, 17, 3, 18. Check: unittest.
2. Contracts and docs.
3. Skills and the skill tests. Check: unittest and validate.
4. Installer. Check: `uv run --locked pytest` and `uv build`.
5. Versions and `build-plugin.sh`.

### 🟡 R14. The glossary scope contradicts §6

§6 lists nine glossary terms, and entry 20 lists five.

**Fix:** make the two lists agree, using the five terms: Period note, Week note, Month note, Recurrence list (*avoid: hub*) and Occurrence. Name the `## Period notes` heading and give each definition word for word.

### 🟡 R15. Wording errors in the plan (style)

- **Line 791** lists "0, 1 and 2 recurring pairs" as Skipped. One pair is the valid case. **This is the author's error.**
- **Manual step 2** checks for `Unchanged`, but the skill reports only `Wrote`, `Skipped` and `Warning`. Either add `Unchanged` to what the skill reports, or reword the step.
- **The bullets under "After `plan_week.py`" in entry 6** mix imperative and passive voice, repeat the broken-marker rule, and put the exit-code handling under the wrong step. "The vault steps" is undefined. Rewrite them as imperatives and move the exit-code bullet under "Before the pool".
- **Entry 4's Invariants** gives no replacement text. This is covered by R2.

### 🟢 Nits (grouped)

- **Tests:**
  - `SetupSkillTest` is a new class, not one to extend.
  - Add a W53 case to `months_touched`: `["2026-12", "2027-01"]`.
  - Add the remaining exit-2 cases to the tests.
  - Add a test that the starter `Recurring.md` produces no warnings. That means its header never contains `every:` outside a fence.
  - Say that CUJ 2 is checked by hand.
- **Interfaces:**
  - Give `markers()` a named result type in place of `Skip | Warn`.
  - Spell out what `False` means in `plan_days(..., False)`.
  - The obsidian-vault folder table has three columns, and `Recurring.md` is a file, not a folder.
  - Name the starter source path and the copy call.
- **Wording:**
  - Use one notation for the ISO filename.
  - Say "planner folder", not "tools folder".
  - Say "still processed", not "still written".
  - Format skill names the same way every time.
  - Say "the user", not "your".
  - Use "fenced code block" consistently.
  - Renumber entry 5a.
  - Add the missing **Why** lines.
  - Decide whether to keep `*Drafted with EGM*`.
- **Open item:** whether to update `cli.py`'s menu label "Update existing vaults (task board)".

## Elephant notes

- **R1, R2, R3, R7 and R11 are verified** against the files cited.
- **R4 is a real gap** that Stage 8 created when the plan section moved to the skill. The plan's rows are `- [ ]` checkboxes, so the transform must drop the box, or the "no checkboxes" rule is broken on the first run.
- **R7 and R8 are reuse choices.** Moving `write_atomic`, `parse_vaults`, `parse_day` and `iso_date` into `planner_config.py` touches `triage.py` and `task_queue.py`. Their existing tests must stay green. That cost is lower than keeping two copies.
- **None of these findings contests** the scope or any decision you made.

---

# Stage 9 re-audit (after the fixes)

**Reviewers:** egm-implementation-readiness, egm-codebase-details and egm-style, each in a fresh context. **Range:** lines 609–1059.

| Reviewer | Verdict |
|---|---|
| Implementation readiness | Not ready: 2 Majors, 4 Nits. R1–R15 all resolved. |
| Codebase details | Not ready: 3 Majors, 6 Nits. No other inaccuracies. |
| Style | Revise: 2 Majors, 5 Nits. R15 resolved, 4 wording nits partly done. |

**Combined verdict: not ready yet.** All earlier findings are resolved. There are four new Majors. Each one would turn a phase check red, or put wrong content into a note, and each needs a one-sentence fix. **Verified** means the main session checked the claim against the code.

## Majors

| # | Doc line | Finding | Fix |
|---|---|---|---|
| X1 | 662–664 | **Verified.** `tests/test_triage.py:14,21` copies only `triage.py` into a temporary `tools/` folder. Once `triage.py` imports `write_atomic` from `planner_config`, every triage test fails with `ModuleNotFoundError`. That contradicts "must pass unchanged". | Entry 2 also changes `test_triage.py` setUp to copy `planner_config.py`, the same way `test_task_queue.py:58` already does. |
| X2 | 627, 758, 966 | Phase 1 tests `examples/vault-starter/Recurring.md`, but entry 19 only creates that file in Phase 4. Phase 1 is red. | Move entry 19 into Phase 1. |
| X3 | 902 | **Verified.** `plan_week.py:163-166` writes `## Didn't fit this week` with `- [ ]` rows. The transform would place those rows in the Plan section as if they were planned. | Drop the `## Didn't fit this week` section and its rows. |
| X4 | 917 (and 889) | **Verified.** `test_skill_files.py:84-87` requires the `task_queue.py` stale-tools bullet to come first in "In this skill:". The new morning-startup bullet has no position. | Say "add it after the stale-tools bullet". |

## Phase check fix (Nit, raised by all three reviewers)

- Line 630: Phase 4's check says "after `uv lock` in entry 24", but entry 24 is in Phase 5. Drop the parenthetical.
- Phase 5's check needs `cd setup && uv run --locked pytest`, so the tests run again after the version bump.

## Nits

- **Line 899–901 and 323:** if `ensure` printed no `Wrote`/`Unchanged` line for a vault's week note, skip that vault and name it.
- **Line 943:** also update `obsidian-vault/SKILL.md:64` ("only Inbox may appear").
- **Line numbers:** line 892 cites `plan-week/SKILL.md:151-152`, which should be `:151-153`. Line 645 cites `triage.py:79-91`, which should be `:79-92`.
- **Lines 1002–1003:** say "assertion at" `:440` and `:609`.
- **Line 744:** `tests/test_setup_check.py` already exists, so the entry should say Modify, not Create.
- **Line 808:** add `fail` to the entry 7 list.
- **Lines 744–748:** move the test-approach bullets out of "Type / Scope".
- **Line 616:** the `tasks` reason should read "`obsidian-vault` skill prose only".
- **Wording consistency:**
  - Use `Weekly/<label>.md` in both places (lines 810 and 1051).
  - Write "owned section" with the same capitalization (lines 853 and 944).
  - Format `plan-week` the same way throughout.
- **Entries 24 and 25:** add **Why** lines.

## Checked and fine

- No other module imports the moved helpers. `park_on_end.py:64` has its own `write_atomic`, which is unaffected.
- The setup tests for a second run, dry runs and `--yes` still pass with the Recurring step placed after `actions.py:391`.

The re-audit cap (1) for Stage 9 is now used.

## Resolution

All four Majors, the phase-check fix and the Nits were applied to the design, with two changes from what the findings proposed:
- **X2:** instead of moving entry 19 into Phase 1, the starter-file test moved into entry 19 (Phase 4). Phase 4's check now also runs the unittest suite. The entry numbers stay the same.
- **X3:** §3 already keeps `## Didn't fit this week` on purpose, as `### Didn't fit this week`, so those rows read as unscheduled. The fix makes the skill text in entry 14 say this explicitly, rather than dropping the section.

Review concluded.
