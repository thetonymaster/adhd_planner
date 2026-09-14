---
name: schedule-workflow
description: >
  Set up (or change) an automatic schedule for a planner workflow — run
  capture-triage, morning startup, plan-day, weekly review, etc. at a chosen
  time or cadence. Use when the user says "run this every day at 18:00",
  "each morning", "every Monday", "schedule my triage", or wants to automate
  any of the planner skills. Triggers: schedule, automate, every day/morning/
  week, run at, remind me daily, set a recurring plan.
---

# Schedule a planner workflow

Turns any of the planner skills into a recurring (or one-time) automatic run,
using the scheduled-tasks tool. Always confirm the time and cadence with the
user before creating; the approval dialog is the final confirmation.

## What can be scheduled

| workflow | skill it runs | suggested cadence | cron (local time) |
|---|---|---|---|
| Capture & triage | `capture-triage` | daily 18:00 (EOD) | `0 18 * * *` |
| Morning startup | `morning-startup` | weekdays 08:30 | `30 8 * * 1-5` |
| End-of-day shutdown | `eod-shutdown` | daily 18:00 | `0 18 * * *` |
| Habit check-in | `habit-tracker` | daily 21:00 | `0 21 * * *` |
| Midday reset | `plan-day` | weekdays 13:00 | `0 13 * * 1-5` |
| Weekly plan | `plan-week` | Sunday 17:00 | `0 17 * * 0` |

Only schedule skills that actually exist in `skills/`. (A monthly-setup workflow
is a natural addition but isn't built yet — don't schedule it until it is.) Note
the EOD shutdown already includes triage, so run *either* capture-triage *or*
eod-shutdown at 18:00, not both.

Cron is evaluated in the user's **local timezone** (<YOUR_TIMEZONE>) — use
local times directly. For a one-off ("tomorrow at 3pm") use `fireAt` with an
ISO 8601 timestamp + offset instead of cron.

## Steps

1. **Confirm** the workflow, the exact time, and the cadence (daily / weekdays /
   weekly / monthly / one-time).
2. **Write a self-contained prompt.** Each run starts fresh with no memory of the
   chat, so the prompt must include everything:
   - the project folder `<PLANNER_DIR>`,
   - the timezone `<YOUR_TIMEZONE>` and "use today's date",
   - which skill to follow (path under `skills/`) and the exact commands to run,
   - your preferences relevant to that workflow (work hours 09:00–18:00,
     lunch protected, Pomodoro 25/5 with a 30-min long break after 4, propose-
     first before creating calendar events),
   - the output to produce and that it must not wait for user input.
3. **Create the task** with `create_scheduled_task` (`taskId`, `cronExpression`
   OR `fireAt`, `prompt`, `description`). To change an existing one, use
   `update_scheduled_task`; to see what's set, `list_scheduled_tasks`.
4. **Tell the user** it only runs while the desktop app is open; if the app is
   closed when it's due, it runs on next launch.

## Ready-to-use prompt — daily capture & triage (18:00)

> Run the end-of-workday capture & triage for the ADHD planner project at
> <PLANNER_DIR> (timezone <YOUR_TIMEZONE>, today's
> date). 1) `python3 tools/triage.py parse`; if 0 items, note the inbox was empty
> and stop. 2) Classify each item: bucket (today/soon/eventually), quadrant
> (do/schedule/delegate/delete), minutes (pad ~25%), optional note — keep "today"
> light at EOD, drop low-value items. 3) Write tools/out/decisions.json, then
> `python3 tools/triage.py apply --decisions tools/out/decisions.json --date <today>`.
> 4) Post the Today/Soon/Eventually buckets + priority matrix, note drops, mention
> tools/out/tasks-<today>.json is ready for plan-day, and offer (don't run)
> plan-day + daily-page. Follow skills/capture-triage/SKILL.md. Self-
> contained; don't wait for input.

Swap the skill/commands to schedule a different workflow.

## Notes

- One task per workflow+time. Don't stack duplicates — check `list_scheduled_tasks`.
- Anything that creates calendar events stays propose-first even when scheduled:
  the run should prepare and report the blocks, not silently create them, unless
  the user has explicitly opted into auto-create.
