# Stage 8: Intermediate Zoom Out Review

* **Target:** `docs/designs/task-priority-ranked-hubs.md` (lines 1-850,
  unchanged since Stage 5)
* **Reviewer:** egm-zoom-out, fresh context, given the Stage 5, 6 and 7 reports
* **Standard:** zoom-out-standard
* **Date:** 2026-11-12
* **Question asked:** if every Blocker and Major from stages 5 to 7 were fixed
  by adding text or mechanism, would this still be the simplest design?
* **Verdict:** No. About half of the findings trace to the one-day split rule,
  which the reviewer recommends cutting from this change. Statements about
  Obsidian Bases are untested and not judged.

## 1. The requested fixes, judged

### Blocker: the one-day split rule (lines 58-61, 117-124, 187-209, 336-347)

* It is the source of critic B1 and M1, comprehension B1 and B2, and Stage 5
  M1, M2 and N1.
* Fixing those by addition needs a split algorithm, slug padding, a capacity
  formula shared with `plan_day.py`, and a pinning path for oversized rows.
* The evidence for it is thin: 3 of 97 open tasks exceed a day.
* Recommendation: cut it. Priority, the hub view and a reproducible order do
  not depend on it.

### Major: the `Ranked` view and the `formulas` merge (lines 375-377, 583-588, 784-791)

Comprehension M7 and M8 ask for more specification of an installer path that
serves no goal. Cut the view; keep the template change and the per-hub offer.

### Major: period and capacity (critic M4, Stage 5 M5)

Do not specify arithmetic for the model to do. `plan_days()` already exists in
`plan_week.py` (lines 81-93); the skill should pass one explicit `--week-start`
to both tools. `--day-minutes` goes away with the split rule.

### Nit: Risks section (critic M6)

Add it as a short list, with no new mechanism.

Comprehension M1 to M4 and critic M5, M8 and M9 are cheap text fixes and worth
making.

## 2. Critic B1 (task size): three options

How the code works today: `create-task` and `task-start` ask only for the first
action; `task-park` rewrites `## Next` to one to three actions; `plan_week.py`
treats `minutes` as an opaque number per row.

| Option | Assessment |
|---|---|
| Creation collects the full step list | Adds a question, against the "no new question" goal. The first park trims the list anyway, so it does not hold. Weakest option. |
| A stored `size:` field | Survives parking, but needs writer rules in three skills and an update after partial work. Too much mechanism for 3 oversized notes. |
| Stop calling it task size | Recommended. `minutes` is the sum of the open `## Next` estimates, named "next work". No skill behaviour changes beyond writing `priority` and `due`. |

Under the third option the planner places the task's next block of work. Work
left over is re-parked and comes back on the next run. The "needs an estimate"
and "no next step" lists stay. The "no task is sized by guesswork" goal is
reworded. A `size:` field stays under Future Improvements.

## 3. Smallest rule changes for the bad-plan findings

### Critic M2: stale week file (lines 329-332)

* With a vault, `plan-day` always runs `task_queue.py` for the day and never
  reads `week-tasks-<date>.json` for vault tasks. One path instead of two.
* The extra keys in the week file (line 312) are dropped.
* Cost to state: a day pin made in the week plan is not carried into the day.
* `morning-startup` reads the week file today and needs the same edit.

### Critic M3: `due` against priority (lines 216-227)

* Add one tier: p0 sorts ahead of dated tasks. A dated p5 still outranks an
  undated p1, which is consistent with `due` being a hard limit.
* A larger option is priority first, which removes the period from the rule and
  makes the hub and planner orders identical. It weakens the hard limit, so it
  is the author's call.

### Critic M3: overdue (lines 308-309)

Treat an overdue task as due on the first planned day and respect capacity. One
that does not fit goes to "Didn't fit", marked overdue. This removes the
over-capacity special case.

## 4. Changes before the implementation plan is reviewed

1. **Cut** the one-day split rule: user journey 2, sibling slugs, "larger than
   one day", `--day-minutes`, and the split steps in files 19, 23 and 24.
2. **Specify** `minutes` as open `## Next` work, not task size; reword lines 69
   and 187-204.
3. **Cut** the `Ranked` view and the `formulas` merge (files 4 and 29).
4. **Simplify** the ordering rule: p0 first; overdue respects capacity.
5. **Simplify** `plan-day` and the daily skills: always the queue, one source.
6. **Simplify** the period: one explicit `--week-start` passed to both tools.
7. **Specify** the result of the Obsidian test and what each failure changes,
   before any other file.

## Author-side note on item 1

The one-day rule was stated by the author as a hard rule ("a task should be
taken from start to done in a single session"). The reviewer had no access to
that conversation and judged the rule only by the 3-of-97 count. Cutting the
enforcement mechanism is not the same as dropping the rule: `create-task` can
still be told to keep tasks within a day and to offer a split when work is
plainly larger, as plain skill guidance, with no size check in the planner, no
slug convention and no `--day-minutes`.

## Code paths the reviewer checked

`create-task`, `task-start` and `task-park` skill files; `plan_week.py`;
`plan-week/SKILL.md:137-139`; `morning-startup/SKILL.md:56`; `plan_day.py`
(break handling only).

## Not verified

The vault measurements; `board_plugin.py` (relied on Stage 5); whether another
tool can import `plan_week.py` cleanly, since it loads its config and can exit
at import.

---

# Stage 8 re-audit (the one permitted re-run)

* **Target:** the revised document, 944 lines
* **Reviewer:** egm-zoom-out, fresh context, given all four earlier reports
* **Verdict:** Not ready at the time of the re-audit. 1 Blocker, 3 Major, 2 Nit.
  All were then edited in the document; those edits have not been reviewed.

## The seven requested changes

| # | Change | Status |
|---|---|---|
| 1 | Cut the one-day split rule | Applied; kept as guidance only |
| 2 | `minutes` is next work, not task size | Applied |
| 3 | Cut the `Ranked` view and formulas merge | Applied |
| 4 | p0 first; overdue respects capacity | Applied |
| 5 | Daily skills always use the queue | Partly (see M1, M2) |
| 6 | One explicit week start for both tools | Partly (see B1) |
| 7 | Specify the Obsidian test and its failures | Applied |

## Earlier blockers

* Comprehension B1 (capacity formula): moot, the rule was cut.
* Comprehension B2 (split procedure): moot, nothing enforces a split.
* Critic B1 (size measures next actions): resolved by redefinition.
* Stage 8 blocker (split rule): resolved.

## New findings, and what was changed in response

### B1. The week-start hand-off planned days already past

With no flag, `task_queue.py` planned from today but reported Monday as
`week_start`; the skill passed that Monday to `plan_week.py`, where an explicit
week start plans the whole week. On a Wednesday, tasks would land on Monday and
Tuesday.

*Change made:* the hand-off is removed. The skill gives both tools the same
flags (the user's `--week-start` and `--include-weekend`, or neither), and both
call the same `plan_days` function.

### M1. A daily run ranked a task due tomorrow as undated

With `--date`, the window ended today, so a task due tomorrow fell into the
last tier. Unattended daily runs would also still merge Monday's vault rows.

*Change made:* for a daily run the window ends six days after the day being
planned. The daily skills always skip week-file rows marked as vault rows. The
document now says the week plan is a preview for vault tasks, and the skill says
how many rows it did not show.

### M2. The row label did not match the label the skills use

The document claimed the title matched today's label; today's label is
`<vault>:<slug>: <item>`.

*Change made:* a row's `title` is now `<vault>:<slug>: <first open step>`, with
the bare `<vault>:<slug>` in a separate `task` key, so the existing label rules
for the printed page, the daily note and repeated titles apply unchanged.

### M3. Inbox rows under `--keep-order`

Alternative H said inbox rows keep today's packing, while section 5 placed them
in input order, and a row with no minutes would exit with an error.

*Change made:* the text now says inbox rows follow the vault tasks in a run with
a vault, and a row with no minutes keeps today's default of 25.

### N1. Ordering rule against its goal

*Change made:* the goal now includes priority between date and start date and
names `<vault>:<slug>`; the note about a far `due` is limited to `p1`..`p5`.

### N2. Installer backups and recursion

Two hubs with the same file name in `Projects/` and `Areas/` would overwrite
each other's backup for a vault outside the home folder.

*Change made:* backups keep the parent folder name, and only files directly in
`Projects/` and `Areas/` are considered.

## Checked and fine

Moving `plan_days` into `planner_config.py` is safe: that module does nothing at
import, and the existing tests keep working through the re-exported name. The
original hub line quoted in section 9 matches the three starter files exactly.
