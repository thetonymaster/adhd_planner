---
name: schedule-workflow
description: >
  Put a planner workflow on a repeating automatic schedule, or change/remove one
  that's already set — "run my triage every day at 18:00", "do the morning startup
  each weekday", "every Monday", "stop the nightly habit check-in". This is about
  recurring automation of the planner skills themselves, not about putting an
  appointment on a calendar (add-event) and not about laying today's tasks out as
  focus blocks (plan-day). Triggers: schedule this daily/weekly, automate my
  triage/startup/shutdown, run it every morning, set a recurring planner task,
  change or cancel a scheduled planner run.
---

# Schedule a planner workflow

Turns any planner skill into a recurring automatic run. Always confirm the workflow,
the time and the cadence before creating anything — the approval dialog is the last
checkpoint, not the first.

## What can be scheduled

Cron is evaluated in **UTC**. The table below is already converted for
America/Lisbon (UTC−6, no DST); for any other timezone convert from the value in
`tools/calendars.json` before writing the cron.

| workflow | skill | suggested local time | cron (UTC) |
|---|---|---|---|
| Capture & triage | `capture-triage` | daily 18:00 | `0 0 * * *` |
| Morning startup | `morning-startup` | weekdays 08:30 | `30 14 * * 1-5` |
| End-of-day shutdown | `eod-shutdown` | daily 18:00 | `0 0 * * *` |
| Habit check-in | `habit-tracker` | daily 21:00 | `0 3 * * *` |
| Midday reset | `plan-day` | weekdays 13:00 | `0 19 * * 1-5` |
| Weekly plan | `plan-week` | Sunday 17:00 | `0 23 * * 0` |

Only schedule skills that exist. `eod-shutdown` already includes triage, so run
*either* it *or* `capture-triage` at 18:00 — never both.

## What makes a firing actually work

A scheduled run is a fresh session in the cloud with nobody watching. Three things
decide whether it does anything useful, and all three fail silently if missed:

- **`requires_local_device: true`, and name the planner folder.** The tools and data
  live on the user's computer. Without this the firing has no access to them and
  completes having accomplished nothing.
- **The computer has to be awake and online** when the task fires, for the same
  reason. Say so when suggesting a time — 03:00 UTC is 21:00 in Porto, which is
  fine; 08:00 UTC is 02:00, which is not.
- **Approvals.** Unless the task is set to approve automatically, the run stops at the
  first prompt and waits for an answer that isn't coming. Mention that the user can
  switch it on in the task's own settings.

## Steps

1. **Confirm** the workflow, the exact local time, and the cadence (daily / weekdays /
   weekly / one-off). Convert the local time to UTC and state both back to the user, so
   a bad conversion gets caught before it's buried in a cron string.

2. **Write a self-contained prompt.** Each firing starts with no memory of this
   conversation, so it must carry: the planner folder and the fact that every command
   is `cd ~/mnt/<planner-folder> && …`; "use today's date" and the timezone from
   `tools/calendars.json`; which planner skill to follow; the exact commands; the
   relevant preferences (work 09:00–18:00, lunch protected, Pomodoro 25/5 with a 30-min
   long break after 4, calendar changes propose-first); what to produce; and that it
   must not wait for input.

3. **Create it** with `create_trigger` — `name`, `cron_expression` (or `run_once_at`
   with an RFC3339 timestamp for a one-off), `prompt`, and `requires_local_device: true`.
   Use `update_trigger` to change an existing one and `list_triggers` to see what's set.
   Prefer updating over deleting and recreating: that keeps the task's run history.

4. **Report back** what was created, in local time, and note the awake-and-online and
   approval caveats from above.

## Ready-to-use prompt — daily capture & triage

> Run the end-of-workday capture & triage for the ADHD planner. Work in the connected
> planner folder; every command is `cd ~/mnt/<planner-folder> && …`. Use today's date
> in the timezone from `tools/calendars.json`. 1) `python3 tools/triage.py parse`; if
> there are 0 items, note the inbox was empty and stop. 2) Classify each item: bucket
> (today/soon/eventually), quadrant (do/schedule/delegate/delete), minutes (pad ~25%),
> optional note. It's end of day, so keep "today" light and actively drop low-value
> items. 3) Write `tools/out/decisions.json`, then `python3 tools/triage.py apply
> --decisions tools/out/decisions.json --date <today>`. 4) Post the
> Today/Soon/Eventually buckets and the priority matrix, say what you dropped and why,
> note that `tools/out/tasks-<today>.json` is ready, and offer — don't run — plan-day
> and daily-page. Follow the planner:capture-triage skill. Self-contained; don't wait
> for input.

Swap the skill and commands to schedule a different workflow.

## Notes

- One task per workflow+time. Check `list_triggers` before creating, so a second
  "morning startup" doesn't quietly join the first.
- Anything that creates calendar events stays propose-first even when scheduled: the
  run prepares and reports the blocks, it doesn't silently create them, unless the user
  has explicitly opted into auto-create.
- To stop a workflow, disable or delete its task — don't leave one firing into a folder
  the user has stopped using.
