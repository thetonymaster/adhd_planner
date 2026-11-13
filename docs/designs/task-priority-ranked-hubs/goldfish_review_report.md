# Goldfish Annotated Review Report

Status: resolved (2026-11-12). 21 proposed fixes applied by auto accept; the
contested part of issue 9 was left as written. The applied edits have not been
re-reviewed.

**Target:** `docs/designs/task-priority-ranked-hubs.md` (lines 688-972, plus the
feature-half lines each finding names)

Source of findings: `implementation_readiness_report.md` (Stage 9). 22 findings:
21 proposed fixes, 1 part-contested. Before writing the proposals I read the
passages they depend on: the three daily skills, `plan-week/SKILL.md`,
`tests/test_skill_files.py`, `tests/test_public_text.py`,
`setup/tests/test_actions.py`, `files.py` and `cli.py`. Issue 7's file list is
relayed from the reviewer and not opened.

## Prioritized Findings & AI Suggestions

### [Issue 1] [`egm-implementation-readiness`, `egm-codebase-details`] - Severity: Medium

*   **Affected Scope:** Lines 839-850 (file 16), 420-429 (section 6)
*   **Discrepancy Description:** File 16 says to replace "the open Next items of
    every active task" in three skills. `eod-shutdown` has no such text;
    `plan-day` and `morning-startup` word it differently.
*   **Rationale:** The implementer cannot find the text and must decide what to
    edit.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Confirmed by reading the three files. The plan needs
    one entry per skill with the existing text quoted.
*   ***Proposed Edit:***
    *   Location: file 16, split into 16a, 16b, 16c.
    *   Change:
        *   **16a `plan-day`**: replace the bullet "**Inputs:** when no task
            list is given, offer the open Next items of every vault's active
            task as the task list." with: "**Inputs:** when no task list is
            given, run `task_queue.py --date <target date>` with one `--vault`
            per vault in play and offer its first ten rows as the task list;
            say how many rows were not shown."
        *   **16b `morning-startup`**: replace the bullet "**Step 2, candidates
            for the Top 3:** add the open Next items of every vault's active
            task (and of any task note the user names) to the pool, titled as
            above. …" with: "**Step 2, candidates for the Top 3:** run
            `task_queue.py --date <today>` with one `--vault` per vault in play.
            Add the rows the user confirms from its first ten (and the row of
            any task note the user names) to the pool, with the titles the tool
            wrote; say how many rows were not shown."
        *   **16c `eod-shutdown`**: add a bullet to the "In this skill" list,
            before the existing "**Step 6:**" bullet: "**Step 6, tomorrow's
            Top 3:** run `task_queue.py --date <tomorrow>` with one `--vault`
            per vault in play and offer its first ten rows as candidates."

### [Issue 2] [`egm-codebase-details`, `egm-implementation-readiness`] - Severity: Medium

*   **Affected Scope:** Lines 846-847 (file 16), 426-429 (section 6)
*   **Discrepancy Description:** Only `morning-startup` reads
    `week-tasks-<today>.json`, in step 2 and in its scheduled prompt. The plan
    applies the "skip vault rows" rule to three skills and names neither place.
    `tests/test_skill_files.py:42-43` pins that path at exactly 2 occurrences.
*   **Rationale:** The obvious edit repeats the path and fails the test.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Confirmed. The rule belongs to `morning-startup` only.
*   ***Proposed Edit:***
    *   Location: section 6 and file 16b.
    *   Change: Section 6 says the week file is read by `morning-startup` only,
        and that skill leaves out its rows marked `"source": "vault"` in step 2
        and in the scheduled prompt. File 16b adds, in both places, after
        "whichever exist,": "leaving out week-plan rows marked
        `"source": "vault"`,". The sentence must not repeat the file path, so
        the three pinned counts in `tests/test_skill_files.py` (pool phrase,
        `plan_day.py --tasks`, week-file path) stay at 2.

### [Issue 3] [all three reviewers] - Severity: Medium

*   **Affected Scope:** Lines 834-835, 847-848, 856; section 5 lines 404-406
*   **Discrepancy Description:** Where the `tools/task_queue.py` check goes, its
    wording and its failure action are not stated. The existing stale-folder
    check sits in a block a test requires to be identical in all 12 planner
    skills. The `--vault` name with no `vaults.json` is undefined.
*   **Rationale:** Placing it in the shared block breaks
    `tests/test_public_text.py`.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Confirmed at `tests/test_public_text.py:55-68`.
*   ***Proposed Edit:***
    *   Location: section 5, files 15 and 16.
    *   Change: The check is the first bullet of the vault block's "In this
        skill" list in the four planning skills, outside the shared
        `where-this-runs` block, worded: "If
        `<planner-path>/tools/task_queue.py` is missing, the folder's tools
        predate this plugin version: say so, offer `planner:setup`, and stop.
        Do not build the task list by hand." With no `vaults.json`, the skill
        passes `--vault vault=<path>`, the name the installer already uses for
        a single unregistered vault.

### [Issue 4] [`egm-implementation-readiness`] - Severity: Medium

*   **Affected Scope:** Lines 772-778 (file 9); section 1 lines 222-240
*   **Discrepancy Description:** The frontmatter and `## Next` readers leave
    cases undefined: list and quoted values, comments, forms of `up:`, a vault
    with no `Tasks/`, a note with no frontmatter, hour rounding, `detail`
    strings, summary layout.
*   **Rationale:** A standard-library parser needs each case decided.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid; each is a choice the implementer would
    otherwise make.
*   ***Proposed Edit:***
    *   Location: section 1 (new "Frontmatter reading rules" list) and section 4.
    *   Change:
        *   Frontmatter is the lines between a first line `---` and the next
            `---` line. A file that does not start with `---`, or is not UTF-8,
            is `unreadable note` whatever its status.
        *   A scalar is the text after `key:`, trimmed, with a trailing
            ` # comment` removed and one pair of matching quotes removed.
        *   `aliases`: an inline list `[a, b]` gives `a`; a block list gives the
            first `- ` line under the key; empty gives none.
        *   `up`: the text between the first `[[` and `]]`, without anything
            from `|` on and without a folder prefix up to the last `/`. `[[]]`
            or no link gives an empty `hub`.
        *   A `--vault` path with no `Tasks/` folder exits 2 naming the path.
        *   Estimate pattern: `(~N min)` or `(~N h)` at the end of the line,
            optional spaces after `~` and before the unit, N an integer or
            decimal. Hours convert per step, rounded up per step. `(~30min)`
            and `(~1.5 h)` both match (30 and 90).
        *   `detail` strings: `N of M open steps have no estimate`;
            `no open step under ## Next`; `not UTF-8` or `no frontmatter`.
        *   Text summary after the task lines: a blank line, then per reason
            `Not placed (<reason>):` and `- <task>: <detail>` lines, then
            `Warnings:` and `- <task>: <field> "<value>": <detail>` lines.

### [Issue 5] [`egm-codebase-details`, `egm-implementation-readiness`, `egm-style`] - Severity: Medium

*   **Affected Scope:** Lines 785-788 (file 10); section 5 lines 386-402
*   **Discrepancy Description:** The plan-line format under `--keep-order`, what
    applies without the flag, and the code shape are not fixed.
*   **Rationale:** "No change without the flag" conflicts with "show priority"
    and "carry `source`". `distribute()` is called positionally by a test.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: section 5 and file 10.
    *   Change: A plan line under the flag is
        `- [ ] <title> — <minutes>m · <priority> (due <deadline>) (overdue)`,
        each of the last three parts present only when it applies, in that
        order. The priority label, the `(overdue)` mark and the `source` key in
        the week files appear only with the flag; without it the output is
        byte-for-byte what it is now. Code shape: `distribute(tasks, day_dates,
        capacity, keep_order=False)`, so the existing positional call in
        `tests/test_plan_week.py` keeps working.

### [Issue 6] [`egm-implementation-readiness`, `egm-codebase-details`] - Severity: Medium

*   **Affected Scope:** Lines 914-924 (file 25); section 9 lines 487-507; CUJ 6
*   **Discrepancy Description:** The installer step leaves open: whether the
    template step asks, missing-file behaviour, key order, how the Base block is
    extracted, where the original hub line lives, function names and prompt
    strings.
*   **Rationale:** `setup/tests/test_actions.py:435-440` asserts the exact list
    of prompts, and its fixture has no `Templates/` or `Projects/` folder.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Confirmed by reading the test. The choices below keep
    that test passing unchanged.
*   ***Proposed Edit:***
    *   Location: section 9, file 25, CUJ 6.
    *   Change:
        *   **Template keys** (`_add_priority_keys(ctx, vault, backups)`): no
            prompt, like the existing "added" case of the Base merge. It says
            "Add" or, on dry-run, "Would add". `priority: p3` goes after `up:`
            (after `status:` with no `up:`; first in the frontmatter with
            neither), and `due:` goes directly after `priority:`. A vault with
            no `Templates/Task.md`, or one with no frontmatter, gets one
            message saying the keys were not added, and the update continues.
        *   **Hubs** (`_replace_hub_tasks(ctx, vault, backups)`): the original
            line is a constant in `actions.py`, since file 2 removes it from
            the starter. The Base block is the text under the `## Tasks`
            heading of the starter `Templates/Project.md` to the end of the
            file, fences included, trimmed. With nothing to replace there is no
            prompt. Otherwise the prompt is
            `Replace the Tasks section in <n> note(s) in <vault>? (backups kept)`.
            Declined: one message, nothing written, exit code unchanged.
        *   **CUJ 6**: "one confirmation per vault" becomes "the Task template
            gains the keys without a prompt; unedited hubs are replaced after
            one confirmation per vault".

### [Issue 7] [`egm-codebase-details`, `egm-implementation-readiness`] - Severity: Medium

*   **Affected Scope:** Lines 936-941 (file 27)
*   **Discrepancy Description:** Five places that describe `update-vaults` as
    task-board only are not in the plan.
*   **Rationale:** They would be left stale.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** `cli.py:34` confirmed by reading. The other four are
    relayed from the reviewer; the implementer confirms each when editing.
*   ***Proposed Edit:***
    *   Location: file 27, extended.
    *   Change: Add `setup/src/planner_setup/cli.py` (the `update-vaults` help
        text), the `update_vaults` docstring in `actions.py`,
        `setup/src/planner_setup/EGM.md`, `setup/src/EGM.md` and the root
        `EGM.md`, each to say the update also adds the Task template keys and
        the hub task list.

### [Issue 8] [`egm-implementation-readiness`, `egm-codebase-details`] - Severity: Medium

*   **Affected Scope:** Lines 503-505 (section 9), 921-923, 933-934
*   **Discrepancy Description:** The backup rule and its test do not match
    `files.backup`, which already keeps the home-relative path for a vault
    inside the home folder. Only vaults outside home collide.
*   **Rationale:** A test with an inside-home vault passes without the fix.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Confirmed at `files.py:34-47`.
*   ***Proposed Edit:***
    *   Location: section 9, files 25 and 26.
    *   Change: Section 9 says: "Each hub is backed up into a folder named after
        its parent folder (`Projects` or `Areas`) under the vault's backup
        folder, so two hubs with the same file name never share a backup path,
        including for a vault outside the home folder." The path example is
        removed. File 26's backup case uses a vault outside home with
        `Projects/X.md` and `Areas/X.md`, modelled on the existing
        `test_update_vaults_keeps_separate_backups_for_vaults_outside_home`.

### [Issue 9] [`egm-implementation-readiness`] - Severity: Medium

*   **Affected Scope:** Lines 693-710 (step 0), 726-727
*   **Discrepancy Description:** The Base block that files 2, 3 and 25 use is
    decided in step 0; two fallbacks give no encoding; the hub view has only
    manual verification.
*   **Rationale:** The implementer must design the fallbacks.
*   ***AI Suggestion:*** PROPOSE FIX for the fallbacks; CONTEST "not in the plan"
    and "only manual verification".
*   ***Justification:*** The block is in section 8 and step 0 exists to confirm
    it before any file is written; no reviewer or author here can run Obsidian.
    A rendered Base view cannot be checked by this repo's test suites, so
    manual verification is the only kind available. The fallback encodings are
    a real gap.
*   ***Proposed Edit:***
    *   Location: step 0 table.
    *   Change: Fallback (b): one formula, `order`, that joins `"0"` or `"1"`
        for not-first, `"0"` or `"1"` for not-soon, the `due` date or
        `9999-12-31`, and `prio`, sorted ascending. Fallback (c): a formula
        `dueKey` that is `due` when set and the date `9999-12-31` otherwise,
        used as the sort key in place of `due`. Both stay marked untested.

### [Issue 10] [`egm-implementation-readiness`, `egm-style`] - Severity: Medium

*   **Affected Scope:** Lines 803-821 (files 13, 14), 903-910 (file 24), 931-934
*   **Discrepancy Description:** Several behaviours have no named test, and the
    test list for `test_task_queue.py` is one long sentence.
*   **Rationale:** Untested behaviour can drift without notice.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid.
*   ***Proposed Edit:***
    *   Location: files 13, 14, 24; a new test entry for file 11.
    *   Change: File 13 becomes a bulleted list, one case per bullet, and adds:
        `unreadable note` (not UTF-8; no frontmatter); the content of
        `warnings`; the text summary; exit 0 when every task is `not_placed`;
        the `name` chain (alias, heading, slug); the `hub` forms from issue 4;
        `task` as a bare slug with one vault. File 14 adds: `source` carried
        into the week files with the flag and absent without it; a pinned row
        under the flag; the plan-line format of issue 5. File 24 adds
        assertions that the three daily skills contain "first ten rows", that
        `morning-startup` contains `"source": "vault"` twice, and that
        `task-note` contains the Log form of issue 15. `tests/test_pdf_hint.py`
        is not touched; the `setup_check.py` list gets one case in a new
        `tests/test_setup_check.py` that removes `task_queue.py` from a copy of
        the tools folder and expects it to be reported.

### [Issue 11] [`egm-codebase-details`, `egm-implementation-readiness`] - Severity: Low

*   **Affected Scope:** Lines 825-837 (file 15)
*   **Discrepancy Description:** `plan-week/SKILL.md` keeps text that is wrong
    for vault runs: the "most room" behaviour note and the step 3 command. A
    test forbids the literal `--week-start <YYYY-MM-DD>` in that skill.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Confirmed at `plan-week/SKILL.md:70-73, 148-150` and
    `tests/test_skill_files.py:29`. The "ask before including parked ones"
    sentence is inside the Backlog bullet that file 15 already replaces.
*   ***Proposed Edit:***
    *   Location: file 15.
    *   Change: Add: after the step 3 command, one line saying a vault run adds
        `--keep-order`; in "Behavior notes", extend the placement bullet with
        "In a vault run, tasks go in rank order on the earliest day with room."
        The skill text refers to "the same `--week-start` value" and never
        writes the forbidden literal.

### [Issue 12] [`egm-codebase-details`] - Severity: Low

*   **Affected Scope:** Lines 855-866 (files 17, 18)
*   **Discrepancy Description:** The script count "ten" appears three times in
    `setup/SKILL.md` and once in `plugins/planner/EGM.md`, which also lists the
    tools by name; `plugins/planner/README.md:33` says "plan-week pulls open
    Next items".
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Relayed line numbers; cheap to state.
*   ***Proposed Edit:***
    *   Location: files 17 and 18.
    *   Change: File 17 names all three "ten" occurrences. File 18 names the
        count and the tool list in `plugins/planner/EGM.md` and the "pulls open
        Next items" sentence in the README.

### [Issue 13] [`egm-codebase-details`] - Severity: Low

*   **Affected Scope:** Lines 766-768 (file 8)
*   **Discrepancy Description:** `planner_config.py` has no `datetime` import,
    so `plan_days` cannot move there "unchanged".
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: file 8.
    *   Change: "Move `monday_of` and `plan_days` here from `plan_week.py` with
        their bodies unchanged, and add the `datetime` import they need."

### [Issue 14] [`egm-implementation-readiness`, `egm-style`] - Severity: Low

*   **Affected Scope:** Lines 690-691
*   **Discrepancy Description:** "The groups in order" contradicts "group 2 can
    be built in parallel"; no check command per group.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: the work-order paragraph.
    *   Change: "Step 0 first. Groups 1 and 2 are independent of each other;
        groups 3, 4 and 5 follow in order. After group 2 run
        `python3 -m unittest discover -s tests`; after groups 3 and 4 run that
        and `claude plugin validate` on the plugin; after group 5 run
        `cd setup && uv run pytest`. The version bumps and the rebuild of
        `planner.plugin` come last."

### [Issue 15] [`egm-implementation-readiness`] - Severity: Low

*   **Affected Scope:** Lines 891-894 (file 22); section 7
*   **Discrepancy Description:** The full Log line, the form when `due` is
    cleared, and the reply on an invalid value are unstated.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:***
    *   Location: section 7 and file 22.
    *   Change: The Log line is `- [[YYYY-MM-DD]] HH:MM — priority p3 → p1`,
        `… — due (none) → 2026-11-20` or `… — due 2026-11-20 → (none)`, with
        date and time taken as the other `task-note` actions take them. On an
        invalid value the skill writes nothing and replies with the accepted
        values.

### [Issue 16] [`egm-style`] - Severity: Low

*   **Affected Scope:** Line 773 (file 9)
*   **Discrepancy Description:** "Everything in Technical Plan sections 1, 2 and
    4:" is unbounded and the list after it reads as partial.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Change to "Implement Technical Plan sections 1, 2 and
    4. Components:" followed by the existing list as bullets.

### [Issue 17] [`egm-style`] - Severity: Low

*   **Affected Scope:** Line 955
*   **Discrepancy Description:** "The three vaults" appears only here.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Change to "over every registered vault".

### [Issue 18] [`egm-style`] - Severity: Low

*   **Affected Scope:** Lines 820, 837
*   **Discrepancy Description:** "today's order", "today's text" are ambiguous
    in a document about dates.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Change to "the current order" and "their current text".

### [Issue 19] [`egm-style`] - Severity: Low

*   **Affected Scope:** Lines 698, 732, 742
*   **Discrepancy Description:** "check each item", "the same replacement as the
    template", "a short section" are loose.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "run checks (a) to (e)"; "apply the file 2
    replacement"; "add a section with…".

### [Issue 20] [`egm-style`] - Severity: Low

*   **Affected Scope:** Lines 844-845 (file 16)
*   **Discrepancy Description:** Comma splice.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Removed by the rewrite of file 16 in issue 1.

### [Issue 21] [`egm-style`] - Severity: Low

*   **Affected Scope:** Lines 855, 869, 929
*   **Discrepancy Description:** Noun phrases where the other entries use
    imperatives.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Change the script count…"; "Rebuild with…"; "Add tests
    for…".

### [Issue 22] [`egm-codebase-details`] - Severity: Low

*   **Affected Scope:** Lines 503-505
*   **Discrepancy Description:** The backup path example in section 9 holds only
    for a vault outside home.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Covered by issue 8, which removes the example.
