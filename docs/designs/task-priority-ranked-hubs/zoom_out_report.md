# Stage 5: Initial Zoom Out Review

* **Target:** `docs/designs/task-priority-ranked-hubs.md` (lines 1-850)
* **Reviewer:** egm-zoom-out, fresh context
* **Standard:** zoom-out-standard
* **Date:** 2026-11-12
* **Verdict:** Context is sufficient and the design addresses the root problem.
  0 Blockers, 5 Major, 4 Nit.

## Major

### M1. The scope bundles three features (lines 17-26, 484-491, 559-820)

Rank fields, the planner rewrite and the one-day split rule ship together across
33 file entries. Alternative J (ship in two parts) is rejected only with "the
author chose to keep the scope whole", which is not a technical reason. The hub
view still rests on an untested Obsidian Bases question. Either stage the work
(fields, hub view and `task_queue.py` first) or state why the split rule must
land in the same change.

### M2. Derived size is weakest where it is used most (lines 187-204, 463-464)

`task-park` rewrites `## Next` to one to three actions
(`plugins/tasks/skills/task-park/SKILL.md:9`). The document counts 89 of 97 open
tasks as parked, so much of the backlog can under-report its size. The stated
acceptance ("a task is meant to be finished in the session that starts it")
contradicts that count. The "larger than one day" check will rarely fire for
existing notes; say so, or drop that check from the planner for now.

*Author-side note:* `parked` is also the status `create-task` gives a task that
was never started, and those notes have never been through `task-park`. How many
of the 89 were started and then parked has not been measured, so the size of
this problem is unknown, not zero.

### M3. "One rule written once" is not what the design delivers (lines 62-64, 213, 373-377)

The hub uses a fixed 7-day window and has no `started` or slug tie-break, so it
is a second rule that can give a different order from the planner. The goal
should say the hub is an approximation. Whether Bases can express even that is
untested.

### M4. The `Ranked` view in `Tasks.base` serves no stated goal (lines 375-377, 583-588, 784-791)

The goal is a list per hub. `merge_base` in
`setup/src/planner_setup/board_plugin.py:83-117` hard-codes two views and has no
handling for a `formulas` block, and the starter `Tasks.base` has none. The view
therefore needs a new formulas merge with its own conflict rule. Cut the view,
or justify it.

### M5. The period and the day limit have two sources (lines 260-265)

The skill is asked to supply `--from`, `--to` and `--day-minutes`. `plan_week.py`
works out its own days from the system date (line 190) and computes capacity
inside `main()` (lines 194-202); no tool exposes either value. The model would
redo that arithmetic, which is the lack of reproducibility the design sets out
to remove. Simpler: `task_queue.py` imports `planner_config` as `plan_week.py`
does, or `plan_week.py` prints the values.

## Nit

* **N1 (lines 198-200):** Oversized tasks sit in `not_placed`, not in `tasks`.
  The document does not say how such a row gets a `day` pin and reaches
  `plan_week.py`.
* **N2 (lines 303 vs 316-319):** "Scheduled runs are unaffected" conflicts with
  the new rule that an unattended run skips a week that already has a plan. That
  rule also changes behaviour for users with no vault.
* **N3 (lines 178-185, 312):** p0 "Today" and p1 "This week" overlap with `due`.
  The extra `priority` and `deadline` keys in `week-tasks-*.json` have no
  consumer beyond checking by eye.
* **N4 (lines 320-323, 817-820):** A broken line wrap, and file 33 lists the
  document itself.

## Verified by the reviewer by reading code

* `plan_week.py`: sort is deadline then largest first; the day chosen has the
  most room; default is 25 minutes; pinned rows ignore capacity; hand-off rows
  hold only `title` and `minutes`; an unknown flag is rejected (argparse).
* `plan_day.py` keeps input order and reads only `title` and `minutes`.
* No frontmatter or `(~N min)` reader exists under `plugins/planner/tools`, and
  plugins may not import each other, so a new reader in `task_queue.py` is
  justified.
* The `Project.md` one-line Tasks pointer and Meetings block exist; the test
  that pins `started` above `finished` and the 400-character limit exist.
* `update_vaults` has backup and dry-run. No hub-editing code exists, so the
  hub migration is new work.

## Not verified

* The vault measurements (97, 89, 76, 425 minutes).
* "About 360 minutes" of usable capacity.
* The script count in `setup/SKILL.md`.
* The `task-note`, `create-task` and `task-start` skill text.
* "Existing readers ignore unknown keys" for `resolve.ts` and `board.ts`.

## Untested (Obsidian Bases, not judged)

Formula defaults, multi-key sort, where an empty `due` sorts,
`today() + "7 days"`, and `this.file` inside an embedded block.
