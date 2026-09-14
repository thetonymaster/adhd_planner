---
name: break-down-task
description: >
  Break ONE big, vague, or overwhelming task into small, concrete, startable
  subtasks with time estimates, sized to ~25-minute focus sessions. Use when the
  user has a single task that feels too big to begin and needs next actions:
  "break this down", "where do I even start with X", "turn X into a plan". For
  sorting a whole pile of mixed thoughts and to-dos, use capture-triage instead;
  to time-block the resulting subtasks into the day, hand off to plan-day.
  Triggers: break down, break this into steps, too big to start, where do I
  start, what are the subtasks, next actions for X.
---

# Break down a task

Turn one big thing into a short list of startable subtasks with estimates.

## Method

1. **Get the goal.** Ask what "done" looks like in one sentence if it isn't clear.
2. **Split into concrete actions.** Each subtask must be:
   - a physical next action ("draft the intro section", not "work on doc"),
   - startable without deciding anything else first,
   - roughly **10–90 minutes**. Anything longer, split again.
3. **Estimate minutes** honestly, then round to multiples of 25 where sensible
   (25 = one focus session, 50 = two, 75 = three). ADHD tip: estimates run low —
   pad by ~25%.
4. **Order** by either sequence (dependencies) or by the ADHD-friendly warm-up
   rule: one quick win first to build momentum, hard/important thing second
   while fresh, admin last.
5. **Cap the day.** More than ~5–6 focus hours of tasks won't fit a 9–18 day
   with meetings — flag overflow and suggest what to move.

## Output

Write a `tasks.json` the scheduler consumes:

```json
[
  {"title": "Draft Q3 planning doc — outline + intro", "minutes": 75},
  {"title": "Review open pull requests", "minutes": 50},
  {"title": "Prep 1:1 notes", "minutes": 25}
]
```

Save it (e.g. `tools/out/tasks.json`). Then hand off to the **plan-day** skill
to slot these around the user's real calendar and produce the planner
checklist.

## Notes

- Keep titles short enough to hand-copy into a planner line.
- If the user gives several unrelated tasks (not one big one), skip the
  splitting and just estimate + order them.

## Where this fits

This skill owns *how* to split a task; it doesn't schedule. The division of
labor across the planner skills:

- **capture-triage** — many mixed thoughts → sorted buckets + a task list.
- **break-down-task** (this) — one big task → subtasks with estimates.
- **plan-day** — a task list → time-blocked focus sessions around the calendar.

`plan-day` calls this skill automatically when it's handed a task that's too big
to schedule as a single block, so you rarely need to run both by hand — but this
skill is also perfectly useful on its own when the user just wants the steps.
