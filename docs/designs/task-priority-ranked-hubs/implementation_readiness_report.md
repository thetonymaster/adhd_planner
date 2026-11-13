# Stage 9: Implementation Readiness Test

* **Target:** `docs/designs/task-priority-ranked-hubs.md`, lines 688-972
  (Detailed Implementation Plan), read against the feature half as its source
  of truth
* **Reviewers:** egm-implementation-readiness and egm-codebase-details (both
  against implementation-readiness-standard), egm-style. Each ran in a fresh
  context.
* **Date:** 2026-11-12
* **Verdict:** Not ready. 0 Blockers, 10 Major, 12 Nit after merging duplicates.
  Each Major leaves the implementer a design choice or would break a test that
  pins existing text. Statements about Obsidian Bases are untested.

## Major

### M1. File 16 names text that two of the three daily skills do not contain (lines 839-850, 420-429) [readiness, codebase]

* `eod-shutdown/SKILL.md` (lines 132-152) has no bullet that sources tomorrow's
  tasks and no pool-merge step. The plan must say which step calls
  `task_queue.py --date <tomorrow>` (step 6, the Top 3 and `plan_day.py`).
* `plan-day/SKILL.md:155-156` reads "offer the open Next items of every vault's
  active task as the task list". It never reads `week-tasks`, so the "skip
  vault rows" rule has nothing to attach to there.
* `morning-startup/SKILL.md:136-139` reads "add the open Next items of every
  vault's active task (and of any task note the user names)".
* The plan must give the exact replacement per skill.

### M2. The week-file skip applies to one skill and collides with pinned text (lines 846-847, 426) [codebase, readiness]

* Only `morning-startup` reads `week-tasks-<today>.json`: in step 2 (line 56)
  and in its scheduled prompt (line 179). The plan names neither, and "attended
  and unattended alike" requires the scheduled prompt to change too.
* `tests/test_skill_files.py:42-43` pins exactly 2 occurrences of
  `tools/out/week-tasks-<today>.json`, and lines 35-40 pin the pool phrase and
  the `plan_day.py --tasks` strings at 2 each. A skip sentence that repeats the
  path fails that test.

### M3. Where the `tools/task_queue.py` check goes is undecided (lines 834-835, 847-848, 856) [all three]

The existing stale-folder check sits inside the shared `where-this-runs` block,
which `tests/test_public_text.py:55-68` requires to be identical in all 12
planner skills. The plan must say the new check goes outside that block (for
example in the vault block's "In this skill" list) or list all 12 skills, give
its wording, and state the action on failure. The `--vault` name to pass when
there is no `vaults.json` is also undefined.

### M4. The frontmatter and `## Next` readers are underspecified (lines 772-778) [readiness]

Undefined cases:

* `aliases` as an inline list (`[Set up vault]`, as in the starter) versus a
  block list.
* Quoted scalars and trailing `# comments`.
* `up: "[[Hub|alias]]"`, `[[Folder/Hub]]`, and the template's `"[[]]"`.
* A vault path with no `Tasks/` folder.
* A note with no frontmatter: it is "unreadable", but it has no readable
  `status` to pass the open-task filter.
* Hours: rounding per step or on the sum; whether `(~1.5 h)` or `(~30min)`
  match.
* The `detail` strings for `no next step` and `unreadable note`, and the layout
  of `not_placed` and warnings in the text summary.

### M5. The `--keep-order` output and code shape are not fixed (lines 785-788, 392-398) [codebase, readiness, style]

* Plan lines today are `- [ ] {title} — {minutes}m (due {deadline})`. Where
  `(overdue)` sits relative to `(due …)`, and whether `· p1` appears without the
  flag, are not stated.
* "No change in behaviour without the flag" conflicts with "show priority" and
  "carry `source`", which read as unconditional.
* `distribute()` is called positionally by `tests/test_plan_week.py:43`, so a
  new parameter needs a default. The plan does not name the code shape.

### M6. The installer logic leaves several choices open (lines 914-924, 491-493) [readiness, codebase]

* How the Base block is extracted from the starter `Templates/Project.md`
  (section bounds, fence included or not).
* The original hub line must be a constant in `actions.py`, because file 2
  removes it from the starter. The plan does not say so.
* Function names and signatures, prompt and message strings, exit code on
  decline. Existing tests match on prompt text.
* Whether the Task-template step asks at all. User journey 6 says "one
  confirmation per vault"; section 9 step 1 is silent.
  `setup/tests/test_actions.py:435-440` asserts the asked list equals the
  download prompts only, and its fixture has no `Templates/` folder, so a new
  prompt or an error there breaks it.
* Key order: with `priority:` present and `due:` missing, "directly after
  `up:`" puts `due` above `priority`.
* A missing `Templates/Task.md`, or one with no frontmatter.

### M7. Installer files missing from the plan (lines 914-941) [codebase, readiness]

These also describe `update-vaults` as task-board only and are not listed:

* `setup/src/planner_setup/cli.py:34` (help text)
* `setup/src/planner_setup/EGM.md:36, 110`
* `setup/src/EGM.md:11`
* root `EGM.md:26, 79`
* the `update_vaults` docstring at `actions.py:230`

### M8. The backup rule and its test do not match the code (lines 503-505, 921-923, 933-934) [readiness, codebase]

`files.backup` already keeps the home-relative path for a vault inside the home
folder, so only vaults outside home collide. The proposed fix gives
`<backups>/<name>/Projects/X.md` only in that case. The test must use a vault
outside home, as the existing
`test_update_vaults_keeps_separate_backups_for_vaults_outside_home` does, or it
passes without the fix.

### M9. The Base block is not in the plan (lines 693-710, 726-727) [readiness]

Files 2, 3 and 25 depend on a block decided in step 0. Fallbacks (b)
"concatenates the keys into one string" and (c) "a far-future date" give no
encoding or value. The hub view has only manual verification.

### M10. Behaviours with no named test (lines 803-821, 903-910) [readiness, style]

* `unreadable note`; `warnings` content; the text summary; exit 0 when every
  task is `not_placed`.
* The `hub` and `name` fallback chains; `task` as a bare slug with one vault.
* `source` carried into the week files; pinned rows under `--keep-order`.
* The `setup_check.py` script list.
* Skill text for the ten-row cap, the vault-row skip, and the `task-note` Log
  format.
* The test list for `test_task_queue.py` is one 130-word sentence; make it a
  bulleted list so each case maps to a named test.

## Nit

* **N1 (lines 825-837):** `plan-week/SKILL.md:148-150` ("picks the one with the
  most room"), the step 3 command (72-73) and "ask before including parked
  ones" become wrong for vault runs. `tests/test_skill_files.py:29` forbids the
  literal `--week-start <YYYY-MM-DD>`. [codebase, readiness]
* **N2 (lines 855-857):** "Ten" appears three times in `setup/SKILL.md` (52, 62,
  65) and once in `plugins/planner/EGM.md:79`; file 18 does not mention the
  count or the tool list at `planner/EGM.md:12-16, 28`. [codebase]
* **N3 (lines 766-768):** `planner_config.py` has no `datetime` import; moving
  `plan_days` there "unchanged" needs one added. [codebase]
* **N4:** `plugins/planner/README.md:33` says "plan-week pulls open Next items";
  file 18 should name that line. [codebase]
* **N5 (lines 891-894):** The full Log line (date prefix), the form when `due`
  is cleared, and the reply on an invalid value are unstated. [readiness]
* **N6 (lines 690-691):** "Groups in order" contradicts "group 2 can be built in
  parallel". No per-group check command; groups 2 and 3 change the planner
  before the version bump and rebuild. [readiness, style]
* **N7 (line 773):** "Everything in Technical Plan sections 1, 2 and 4" is
  unbounded; say "implement" and list the components. [style]
* **N8 (line 955):** "The three vaults" appears only here; say "every registered
  vault". [style]
* **N9 (lines 820, 837):** "today's order", "today's text" are ambiguous in a
  document about dates; say "current". [style]
* **N10 (lines 698, 732, 742):** "check each item", "the same replacement as the
  template", "a short section" are loose; name the checks and the file.
  [style]
* **N11 (lines 844-845):** Comma splice; split the sentence. [style]
* **N12 (lines 855, 869, 929):** Noun phrases where other entries use
  imperatives. [style]

## Confirmed against the code

* `plan_days` and `monday_of` are at `plan_week.py:77-93`; week files hold title
  and minutes only; the default is 25 minutes; an overdue row overflows today.
* `plan_day.py:120` ignores extra keys.
* The Backlog bullet quoted for `plan-week` matches `SKILL.md:137-140`.
* The Tasks pointer line is in exactly three starter files, and the Meetings
  block uses `file.hasLink(this.file)`.
* `Templates/Task.md` has `up:` at line 3; the adjacency test is at
  `test_skill_files.py:74`.
* `create-task` steps 2 and 4, `task-start` step 4 and the `task-note` Actions
  table exist as cited. Versions are 0.5.5 and 0.6.1.
* `setup_check.py:49-50` holds the required-scripts list. The skill counts
  (twelve, eight) are unaffected.

## Coverage

* Every file entry maps to a behaviour or a contract update; none is orphaned.
* Technical Plan sections 1, 2, 4, 5 and 9 have file entries and tests, with
  the gaps in M10.
* Sections 6 and 7 are skill text, checked only by keyword assertions.
* Section 8 (hub view) is untested.

## Not opened by the code reviewer

`How this vault works.md`, the starter hubs beyond a search hit,
`plugins/tasks/EGM.md`, `scripts/build-plugin.sh`, and parts of the README and
setup docs. Findings against those rest on search output only.

---

# Stage 9 re-audit (the one permitted re-run)

* **Target:** the plan after the 21 accepted fixes, lines 743-1144
* **Reviewers:** egm-codebase-details and egm-implementation-readiness, fresh
  contexts. The style reviewer was not re-run.
* **Verdicts:** codebase-details: ready to implement from (0 Blockers, 0 Major,
  7 Nit). implementation-readiness: not ready until three short text edits are
  made (0 Blockers, 3 Major, 7 Nit); "fixes that broke something: none found".
* **After the re-audit:** the three Majors and the Nits were edited in the
  document. Those edits have not been reviewed; the re-audit limit is reached.

## Earlier Majors

| ID | Status at re-audit |
|---|---|
| M1 daily-skill text | Resolved |
| M2 week-file skip and pinned counts | Resolved |
| M3 stale-tool check | Partly: placement and wording fixed; the call form did not reach skill text (F1) |
| M4 reader rules | Resolved |
| M5 `--keep-order` output | Resolved |
| M6 installer choices | Resolved, with F2 and two nits |
| M7 missing installer files | Resolved; the file list was confirmed against the repo |
| M8 backup rule | Resolved |
| M9 Base block | Partly, untested: fallbacks stated; the block is still fixed only in step 0 |
| M10 named tests | Resolved, with one nit |

## Confirmed against the code (codebase-details)

* Every piece of existing text the plan quotes is present as quoted, in
  `plan-week`, `plan-day`, `morning-startup`, `eod-shutdown`, `setup/SKILL.md`,
  the planner README and the three starter files with the hub line.
* Every test the plan says must keep passing would pass with the edits as
  worded. For `morning-startup`: the pool phrase, the `plan_day.py --tasks`
  command and the week-file path each stay at 2; `"source": "vault"` goes from
  0 to 2.
* The entry 27 file list and entry 18's claims are correct. A search found no
  other file that must change.

## New findings and the change made for each

### F1 (Major). The skills never received the `task_queue.py` call form

The replacement texts said only "with one `--vault` per vault in play". Nothing
stated the `<name>=<path>` form, the command line, or which file to read back;
for `--date` the default output name depended on a date the model could not
infer.

*Change made:* the default output is now the fixed `tools/out/queue.json`.
Section 4 gives one call form for every planning skill, each skill's
replacement text writes it out in full, and `tests/test_skill_files.py` asserts
it is present.

### F2 (Major). A second `update-vaults` run was undefined

After a yes, replaced hubs held the Base block, which counted as "other text",
so every later run would list them as left unchanged.

*Change made:* a Tasks section that already equals the Base block is counted in
one "already have the task list" line. A second-run test is added.

### F3 (Major). `eod-shutdown` had no entry for sending rows to `plan_day.py`

*Change made:* its new bullet adds the confirmed rows to the task list step 6
passes to `plan_day.py` for tomorrow.

### Nits, all edited

* The warning text for an invalid `due`, and the sort order of `not_placed` and
  `warnings`.
* `<vault>` in the installer prompt is the path.
* The two installer steps run after `_merge_tasks_base` and before
  `_board_plugin`.
* `task-note` adds a missing `due` after `priority:`, matching the template.
* A note with a missing or misspelled `status` is now included in the list
  (anything other than `done`), matching the hub filter.
* Tests added for `--include-weekend`, `--out`, the starter hubs, the vault's
  own `Templates/Project.md`.
* Backups cover `Templates` as well as `Projects` and `Areas`.
* Locations named: `plan-week` step 2; the line break in the scheduled prompt;
  both `planner_config.py` mentions in `setup/SKILL.md`; the second stale
  README sentence; the tools contract's test list and its "scripts read only
  JSON" sentence. New skill-text assertions use `flat()`. The installer menu
  label stays, because a test pins it.

## Still open

* Every statement about the Obsidian Base view is untested until step 0 of the
  plan is run in Obsidian. Files 2, 3 and 25 depend on its result.
