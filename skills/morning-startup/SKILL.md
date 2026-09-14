---
name: morning-startup
description: >
  Run the full morning routine end-to-end: pull today's Google Calendar, set the
  Top 3, break down the day's main task into subtasks, time-block everything
  around the meetings, and print the daily page. This is the "set up my whole
  day" skill — it chains break-down-task + plan-day + planner-daily. Use when the
  user wants their day built from scratch: "plan my day", "good morning set me
  up", "what's my day look like". If they only want to time-block a task list
  they already have (no calendar pull, no printing), use plan-day instead.
  Triggers: plan my day, good morning, start my day, set up today, morning
  routine, get me ready for the day.
---

# Morning startup

Chains the planner skills into one "ready for the day" routine.

## Steps

1. **Pull today's meetings.** Google Calendar `list_events` for today across the
   calendars that hold real commitments (the user's primary, plus family/personal
   if relevant). Save to `tools/out/busy.json`.

2. **Gather today's tasks.** In order of preference:
   - yesterday's `tools/out/tasks-<yesterday>.json` (from capture-triage), and/or
   - `python3 tools/triage.py parse` on `inbox.md` — if there are fresh captures,
     triage them first (see capture-triage), producing `tools/out/tasks-<today>.json`.
   Confirm the **Top 3** for today with the user (or take the top do/schedule items).

3. **Break down the main task** if one is big/vague — run break-down-task to get
   subtasks. Save the day's tasks with subtasks to `tools/out/day-tasks-<today>.json`
   as `[{"title":..,"subtasks":[..]}]`.

4. **Time-block around meetings:**

   ```
   python3 tools/plan_day.py --tasks tools/out/tasks-<today>.json \
       --busy tools/out/busy.json --date <today> --work 09:00-18:00 --lunch 14:00-15:00
   ```

   Read the timed checklist (`tools/out/plan-<today>.md`) back to the user.

5. **Print the daily page:**

   ```
   python3 tools/make_daily.py --date <today> --events tools/out/busy.json \
       --tasks tools/out/day-tasks-<today>.json
   ```

   Share `tools/out/daily-<today>.pdf` with present_files.

6. **Offer** to push the focus blocks to Google Calendar (propose-first, from
   `tools/out/gcal-events-<today>.json`), and to refresh the live dashboard if the
   user set one up. Don't auto-create events.

## Preferences

Work 09:00–18:00, lunch 14:00–15:00 protected. Pomodoro 25/5, 30-min long break
after 4 sessions. Timezone <YOUR_TIMEZONE>. Calendar changes are propose-first.

## Scheduled run (how to automate)

To run automatically on weekday mornings, use the schedule-workflow skill /
`create_scheduled_task` with **cron `30 8 * * 1-5`** (08:30, weekdays, local time)
and this self-contained prompt:

> Run morning startup for the ADHD planner at <PLANNER_DIR>
> (timezone <YOUR_TIMEZONE>, today's date). 1) Google Calendar list_events for
> today (primary + any family/personal calendars) → save tools/out/busy.json. 2) Get today's tasks
> from tools/out/tasks-<today>.json, or parse inbox.md and triage if there are new
> captures. 3) Break down any big task into subtasks →
> tools/out/day-tasks-<today>.json. 4) `python3 tools/plan_day.py --tasks
> tools/out/tasks-<today>.json --busy tools/out/busy.json --date <today> --work
> 09:00-18:00 --lunch 14:00-15:00`. 5) `python3 tools/make_daily.py --date <today>
> --events tools/out/busy.json --tasks tools/out/day-tasks-<today>.json` and present
> the PDF. 6) Post the timed checklist + Top 3; offer (don't run) to push focus
> blocks to Calendar. Follow skills/morning-startup/SKILL.md. Self-contained; don't
> wait for input. Only runs while the desktop app is open (runs on next launch if
> it was closed).

Confirm the time with the user before creating the task.
