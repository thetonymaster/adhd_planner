---
name: eod-shutdown
description: >
  End-of-day shutdown: review what got done, migrate unfinished tasks to
  tomorrow, brain-dump and triage to clear your head, run the wind-down / bedtime
  routine, and seed tomorrow's plan (Top 3, daily page, proposed focus blocks).
  Use when the user says "shut down", "wrap up my day", "end of day review",
  "close out today", or runs the scheduled EOD. Triggers: shutdown, end of day,
  wrap up, close out, evening review, done for the day.
---

# EOD shutdown

Closes today cleanly and sets tomorrow up so mornings start with momentum.
Incorporates capture-triage — if you run this at 18:00 you don't also need a
separate triage run.

## Steps

1. **Review today.** Load today's plan (`tools/out/plan-<today>.md` /
   `tasks-<today>.json`) and, for context, today's calendar via `list_events`.
   Ask the user (or, if unattended, list the planned tasks and mark none done):
   what got **done**, what **didn't**.

2. **Migrate unfinished** to tomorrow's inbox so nothing is lost:

   ```
   python3 tools/triage.py carry --items tools/out/leftover.json
   ```

   where `leftover.json` is a JSON list of the undone task titles. They land in
   `inbox.md` for tomorrow's triage/morning-startup.

3. **Brain-dump to clear your head.** Invite any loose thoughts; append them to
   `inbox.md` (one `- ` line each).

4. **Triage the inbox** (capture-triage): `python3 tools/triage.py parse`, classify
   into buckets + matrix, write `tools/out/decisions.json`, then
   `python3 tools/triage.py apply --decisions tools/out/decisions.json --date <today>`.
   Keep **tomorrow's Today list light** — only what truly must happen.

5. **Wind-down / bedtime routine.** Walk the Sleep-page routine: bedroom set,
   hygiene, tomorrow prep (clothes, bag, keys). Optionally compute a bedtime by
   working backward from the wake time and offer to set a bedtime reminder
   (add-event, propose-first).

6. **Seed tomorrow.** Confirm tomorrow's **Top 3**. Then produce the requested
   outputs:
   - **Shutdown summary in chat** — done vs. undone, what was migrated, tomorrow's Top 3.
   - **Tomorrow's daily-page PDF** — `python3 tools/make_daily.py --date <tomorrow>
     --events tools/out/busy-tomorrow.json --tasks tools/out/day-tasks-<tomorrow>.json`
     (pull tomorrow's calendar first). Present it.
   - **Proposed focus blocks for tomorrow** — run `plan_day.py` for tomorrow and
     offer to push `gcal-events-<tomorrow>.json` to Calendar (propose-first).
   - **Refresh the dashboard** with tomorrow's Top 3 + tasks, if the user set up
     the optional live dashboard (skip otherwise).

## Preferences

Work 09:00–18:00. Pomodoro 25/5, 30-min long break after 4. Timezone
<YOUR_TIMEZONE>. Calendar changes are propose-first. Keep tomorrow realistic.

## Scheduled run (how to automate)

To run automatically at end of the workday, use the schedule-workflow skill /
`create_scheduled_task` with **cron `0 18 * * *`** (18:00 daily, local time) and
this self-contained prompt:

> Run EOD shutdown for the ADHD planner at <PLANNER_DIR>
> (timezone <YOUR_TIMEZONE>). Today = current date, tomorrow = +1 day.
> 1) Review today's plan (tools/out/plan-<today>.md, tasks-<today>.json) and
> calendar. 2) If task completion is unknown (unattended), carry ALL of today's
> planned tasks forward: write their titles to tools/out/leftover.json and run
> `python3 tools/triage.py carry --items tools/out/leftover.json`. 3) Parse +
> triage inbox.md (capture-triage): `python3 tools/triage.py parse`, classify,
> write tools/out/decisions.json, `python3 tools/triage.py apply --decisions
> tools/out/decisions.json --date <today>`; keep tomorrow's Today light.
> 4) Pull tomorrow's calendar via list_events → tools/out/busy-tomorrow.json, run
> `python3 tools/plan_day.py --tasks tools/out/tasks-<today>.json --busy
> tools/out/busy-tomorrow.json --date <tomorrow> --work 09:00-18:00 --lunch
> 14:00-15:00`, and `python3 tools/make_daily.py --date <tomorrow> --events
> tools/out/busy-tomorrow.json --tasks tools/out/day-tasks-<tomorrow>.json`; present
> the PDF. 5) Post a shutdown summary (done/undone, migrated, tomorrow's Top 3) and
> offer (don't run) to push tomorrow's focus blocks to Calendar. Follow
> skills/eod-shutdown/SKILL.md. Self-contained; don't wait for input. Runs only
> while the desktop app is open (on next launch if it was closed).

Note: this 18:00 EOD prompt already includes triage, so use it *instead of* a
separate daily-capture-triage task at the same time. Confirm the time before creating.
