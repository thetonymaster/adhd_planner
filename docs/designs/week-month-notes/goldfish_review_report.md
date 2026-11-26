Status: resolved (auto accept: 16 fixes applied, 1 contested item kept)

# Goldfish Annotated Review Report

**Target:** `docs/designs/week-month-notes.md`, lines 575–879 (Detailed Implementation Plan). Five fixes also touch lines 1–574, the parts of the spec the plan restates: R4, R5, R9, R10 and R14.
**Source:** `implementation_readiness_report.md` (Stage 9), groups R1–R15 and the Nits.

**Summary:** 15 fixes are proposed and 2 Nits are contested. Every proposal was checked against the repo.

## Prioritized Findings & AI Suggestions

### [Issue 1] [`implementation-readiness`, `codebase-details`] - Severity: High
*   **Affected Scope:** Entries 6, 13, 15 and 19 (R1).
*   **Discrepancy Description:** Two existing test files fail as written.
    *   `setup/tests/test_actions.py:440,609` asserts the exact prompt list. The new Recurring prompt adds an entry to it.
    *   `tests/test_skill_files.py:51-55` asserts the stale-tools sentence word for word.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Verified against both files.
*   ***Proposed Edit:***
    *   **Entry 6:** keep the `task_queue.py` stale-tools sentence word for word. Add a second bullet right after it: "If `<planner-path>/tools/period_note.py` is missing, the folder's tools predate this plugin version: say so, offer `planner:setup`, and stop."
    *   **Entry 15:** add "Modify `test_update_vaults_asks_before_download` (`:440`) and `test_update_vaults_adds_the_template_keys_without_a_prompt` (`:609`) to compare only download questions: `[q for q in asked if q.startswith("Download ")]`, the same filter `hub_questions` uses at `:684-685`."
    *   **Entry 19:** say that the existing stale-tools test is unchanged, and that a new assertion checks the `period_note.py` sentence.

### [Issue 2] [`codebase-details`, `implementation-readiness`] - Severity: High
*   **Affected Scope:** Entries 4, 5, 8 and 9, plus a new entry 14a (R2).
*   **Discrepancy Description:** The plan misses these lines:
    *   `setup/SKILL.md:52`, which says "Eleven";
    *   `tools/EGM.md:76`, which says "the one tool that reads a vault";
    *   `tools/README.md:31` and its script table;
    *   setup's three EGM files;
    *   `plugins/planner/EGM.md:26,28,58-61`.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Verified.
*   ***Proposed Edit:***
    *   **Entry 8:** change the count to twelve at lines 52, 63 and 66, and name `period_note.py` in the parenthetical at line 63. The test asserts that "eleven" no longer appears, case-insensitively.
    *   **Entry 4:** replace `tools/EGM.md:76` with "`task_queue.py` and `period_note.py` are the tools that read a vault, only from the `--vault` paths the caller gives. `task_queue.py` writes nothing there. `period_note.py` writes only `Weekly/` and `Monthly/` notes in vaults that have `Recurring.md`." Add an invariant bullet for `period_note.py`'s exit codes, modelled on `:79-81`.
    *   **Entry 5:** rewrite `README.md:31` to match, and add a `period_note.py` row to the script table.
    *   **Entry 9:** add the tool to the morning-startup and plan-week lines (`:26`, `:28`), and add its stale-tools check to `:58-61`.
    *   **New entry 14a:** `setup/src/planner_setup/EGM.md`:
        *   `:86` gets the new question;
        *   `:111` gets `Recurring.md` in the list of files written.

        `setup/EGM.md`:
        *   `:11-13` gets the update-vaults bullet;
        *   `:26` gets version 0.2.0.

        `setup/src/EGM.md:11` gets the actions sentence.

### [Issue 3] [`codebase-details`, `implementation-readiness`, `style`] - Severity: High
*   **Affected Scope:** Entries 6 and 7 (R3).
*   **Discrepancy Description:**
    *   `--include-weekend` would be passed to `ensure`, which doesn't accept it, so the call exits 2.
    *   The morning-startup command has no `cd`, no quoted `--vault`, and uses `<today>`.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Verified `plan-week/SKILL.md:151-152` and `morning-startup/SKILL.md:29-30,144`.
*   ***Proposed Edit:***
    *   **Entry 6:** reword `:151-152` to "Give `task_queue.py`, `plan_week.py` and `period_note.py` the same `--week-start` value when the user asked for one; give `--include-weekend` to `task_queue.py` and `plan_week.py` only." Note that `test_skill_files.py:38-39` forbids the literal `--week-start <YYYY-MM-DD>`.
    *   **Entry 7:** the command becomes `cd "<planner-path>" && python3 tools/period_note.py ensure --date <Now: date>`, with one quoted `--vault "<name>=<vault-path>"` per vault in play. It goes in the "In this skill" list.

### [Issue 4] [`codebase-details`] - Severity: High
*   **Affected Scope:** §3 "Plan section" (L293–318) and entry 6 (R4).
*   **Discrepancy Description:** The design doesn't say how the skill turns `plan_week.py`'s `.md` output into the Plan section. That output contains:
    *   `- [ ]` checkbox rows;
    *   `##` headers;
    *   `_…_` lines;
    *   `- (open …)` placeholder lines;
    *   the `90m` minute format.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:* Verified `plan_week.py:140-169`. The rows are checkboxes, so copying them as written would break the "no checkboxes" rule on the first run.
*   ***Proposed Edit:*** Replace the §3 example and add an exact transform:
    *   each `## <day>` header becomes `### <day>`;
    *   keep only lines that start with `- [ ] `;
    *   drop the `- [ ] ` prefix and the `<vault>:` label;
    *   keep the rest of the row as written, including `90m`, ` · pN`, `(due …)` and `(overdue)`;
    *   drop lines that start with `_`, and `- (open — no tasks assigned)`;
    *   rows under `## Didn't fit this week` go under `### Didn't fit this week`;
    *   drop a day heading that has no rows left for that vault.

    Entry 6 writes this transform into the skill.

### [Issue 5] [`codebase-details`] - Severity: Medium
*   **Affected Scope:** §4 "Output lines" table, the Risks entry on midnight, and entries 2, 6 and 17 (R5).
*   **Discrepancy Description:** Checking that the week label matches the plan's Monday requires the skill to do ISO-week arithmetic in prose.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   `ensure` prints `Week 2026-W48 (Monday 2026-11-23)` as its first line. Add that line to the §4 table.
    *   The skill compares that date with the date in the `weekly-plan-<date>.md` filename.
    *   Add a test for the line.

### [Issue 6] [`implementation-readiness`, `codebase-details`] - Severity: Medium
*   **Affected Scope:** Entries 2 and 17 (R6).
*   **Discrepancy Description:** A subprocess test can't fake Sunday.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Entry 2: `main(argv, today=None)`. Only the `__main__` guard reads `dt.date.today()`, which matches "IO at the edges".
    *   Entry 17: the Sunday case runs in-process with `today=date(2026,11,22)` and expects W48. The CUJ fixtures pass `today` the same way.

### [Issue 7] [`codebase-details`] - Severity: Medium
*   **Affected Scope:** Entry 2 `write_if_changed`, and a new entry 1 sub-item (R7).
*   **Discrepancy Description:** The plan re-implements the atomic write and leaves out three details: keeping the file mode, a dot-prefixed temp name, and cleanup on error.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** `triage.write_atomic` (`triage.py:79-91`) already handles all three.
*   ***Proposed Edit:***
    *   **Entry 1:** move `write_atomic(path, text, prefix)` into `planner_config.py`.
        *   A new file gets mode `0o666 & ~umask`.
        *   It writes encoded bytes, so `\r\n` survives.
    *   **`triage.py` (Modify):** add `from planner_config import write_atomic` and pass `prefix=".inbox-"`. Its tests stay as they are.
    *   **Entry 2:** `write_if_changed` calls `write_atomic(..., prefix=".period-")`.

### [Issue 8] [`codebase-details`, `implementation-readiness`] - Severity: Medium
*   **Affected Scope:** Entry 2 `main`, §4 exit codes and entry 17 (R8).
*   **Discrepancy Description:** Argument validation is incomplete. Leaving it out would also duplicate `task_queue.py`'s parsers.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **Entry 1:** move `iso_date`, `parse_day` and a `parse_vaults(values, require=())` into `planner_config.py`.
        *   `task_queue.py` keeps its names through imports and passes `require=("Tasks",)`.
        *   `period_note.py` passes `()`.
    *   **§4 exit-2 list:** add these cases, each message naming the bad value:
        *   a repeated `--vault` name;
        *   a path that isn't a folder;
        *   an invalid date;
        *   `--week-start` without `--plan-week`;
        *   `--week-start <D> is not a Monday`.
    *   **Entry 17:** one test per case.

### [Issue 9] [`implementation-readiness`, `codebase-details`] - Severity: Medium
*   **Affected Scope:** §3–§4 and entries 2, 13 and 17 (R9).
*   **Discrepancy Description:** Several byte-level choices are left to the implementer.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **Line endings:** inserted and rewritten lines take the ending of the opening `---` line. If the file has no frontmatter, they take the first line's ending; if it has no line ending at all, `\n`.
    *   **A new note with no occurrences:** written with `added: []`, and nothing between its markers. Every new note ends with `## Notes\n`.
    *   **`added:` values:**
        *   An empty value, or `[]`, is an empty ledger.
        *   A scalar such as `added: foo` is treated as a one-ID list.
        *   Quoted IDs are unquoted by the same `scalar` rules `task_queue.py` uses.
        *   No warning in any of these cases.
    *   **Fences:** ``` and `~~~` at column 0 open and close a fence. A `^ID` inside a fence does not count.
    *   **Warning reasons:**
        *   `unknown rule '<r>'`
        *   `month <N> out of range 1–31`
        *   `missing #id/`
    *   **Duplicate IDs:** a single warning lists every line that shares the ID.
    *   **Ledger row 2:** prints no warning unless the `added:` key is missing.
    *   **`update-vaults` decline:** prints `Kept <vault> without Recurring.md (week and month notes stay off).`
    *   **`update-vaults` accept:** prints `Added Recurring.md to <vault>.`

### [Issue 10] [`implementation-readiness`] - Severity: Medium
*   **Affected Scope:** §4 table and entries 2 and 17 (R10).
*   **Discrepancy Description:** Nothing says what happens with files that aren't UTF-8, or with an `OSError`.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Add these rows to the §4 table, each with exit 1, and add one test for each:
    *   `Skipped <vault>:<path>: not UTF-8`
    *   `Skipped <vault>:<path>: <strerror>`

    A `Recurring.md` that isn't UTF-8 means nothing is written to that vault.

### [Issue 11] [`implementation-readiness`] - Severity: Medium
*   **Affected Scope:** Entry 11 (R11).
*   **Discrepancy Description:** Period notes have no `up:`, which conflicts with the obsidian-vault rules for `up:` and dead ends.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **Entry 11:** add "Period notes and `Recurring.md` have no `up:`. The expected dead ends are `Inbox`, `Monthly/*` and `Recurring.md`."
    *   **Folder table:** give the full three-column rows (Template `—`), and add a "Files at the root" line for `Recurring.md`.

### [Issue 12] [`implementation-readiness`, `codebase-details`] - Severity: Medium
*   **Affected Scope:** Entry 22 and the Verification Plan (R12).
*   **Discrepancy Description:** CI checks `uv.lock`, and nothing in the plan regenerates it.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **Entry 22:** run `cd setup && uv lock` and commit `setup/uv.lock`.
    *   **Verification Plan:** run `cd setup && uv run --locked pytest`.

### [Issue 13] [`implementation-readiness`] - Severity: Medium
*   **Affected Scope:** The structure of the Target Files list (R13).
*   **Discrepancy Description:** The list has no phases, and the standard requires phases.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Add a "Phases" table before Target Files, listing each phase's entries and its check command:

    | Phase | Covers | Check |
    |---|---|---|
    | 1 | library and tool | unittest |
    | 2 | contracts and docs | — |
    | 3 | skills and skill tests | unittest + validate |
    | 4 | installer | `uv run --locked pytest`, `uv build` |
    | 5 | versions and build | `build-plugin.sh` |

    Renumber entries 5a and onward.

### [Issue 14] [`implementation-readiness`, `codebase-details`, `style`] - Severity: Medium
*   **Affected Scope:** §6 (L422) and entry 20 (R14).
*   **Discrepancy Description:** The glossary list in §6 contradicts entry 20.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **§6:** "`GLOSSARY.md` gets Period note, Week note, Month note, Recurrence list (*avoid: hub*) and Occurrence. Owned section, Plan section, Recurring section and Ledger go only in the `plugins/EGM.md` invariant."
    *   **Entry 20:** add a new `## Period notes` heading with the five definitions word for word.

### [Issue 15] [`style`] - Severity: Medium
*   **Affected Scope:** Entry 17 (L791), the Verification step on re-runs, and entry 6 (R15).
*   **Discrepancy Description:**
    *   One marker pair, which is the valid case, is listed as Skipped.
    *   The verification step checks for `Unchanged`, but the skill never reports that line.
    *   The bullets in entry 6 use mixed voice.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   **L791:** "no markers, a lone start or end, two pairs, end before start, markers only inside a fence → Skipped".
    *   **Verification step:** "the second run reports no `Wrote` lines".
    *   **Entry 6:** rewrite as imperatives, and move the exit-code handling under "Before the pool".

### [Issue 16] [`style`, `implementation-readiness`] - Severity: Low (Nits)
*   ***AI Suggestion:*** PROPOSE FIX for these:
    *   say that `SetupSkillTest` is a new class;
    *   add a `months_touched` case for W53;
    *   add a test that the starter `Recurring.md` produces no warnings, and keep `every:` out of its header;
    *   say that CUJ 2 is checked manually;
    *   give `markers()` a named result, `MarkerCount(start, end, start_idx, end_idx)`;
    *   use `plan_days(today, week_start, include_weekend=False)`;
    *   name the starter source `paths.examples() / "vault-starter" / "Recurring.md"` with `shutil.copyfile`;
    *   wording: "planner folder", "still processed", "fenced code block", and backticks around skill names;
    *   add the missing **Why** lines;
    *   use `<ISO year>-W<week>` notation in the folder table.

### [Issue 17] [`style`, `implementation-readiness`] - Severity: Low
*   ***AI Suggestion:*** CONTEST
*   ***Justification:***
    *   **`*Drafted with EGM*`:** this footer is the EGM template's own marker, and the sibling design uses it too.
    *   **`cli.py` menu label "Update existing vaults (task board)":** changing it is out of scope. The label still describes the command, and the help text (entry 14) carries the new detail.
