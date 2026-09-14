---
name: habit-tracker
description: >
  Track daily habits with streaks across sleep/bedtime, eating/fuel, and your
  active commitments (from the planner's Sustain + Commitments layouts). Log what
  you did today, see current streaks and 7-day marks, and get a weekly adherence
  review. Use when the user wants to check off habits, "did I keep my streak",
  log a habit, or review how the week went. Triggers: habits, streak, log my
  habits, did I do, habit check-in, weekly habit review, track my routine.
---

# Habit tracker

Daily habit logging with streaks, for sleep, eating, and commitments.

## Where this runs

`tools/` and the data it reads and writes (`calendars.json`, `habits.json`,
`inbox.md`) live in the **connected planner folder on the user's computer**, not in
this plugin — a plugin is read-only, and these files get written. So every command
below runs there, via the device shell.

Each device shell call is a fresh shell with no memory of the last one's working
directory, so the `cd` has to ride along on every command, exactly as written below.
Substitute the real folder name for `<planner-folder>` (check what's connected).

If no planner folder is connected, say so and stop rather than guessing a path —
`planner:setup` seeds a new one from the copies bundled with this plugin.

## Files

- `habits.json` (repo root) — the habits being tracked, grouped by `area`
  (`sleep` / `eating` / `commitment`). Edit freely; set the two commitment
  placeholders to the user's real 1–3 commitments before first use.
- `habits-log.json` (repo root) — the daily marks. Managed by the script.

## Commands

```
cd ~/mnt/<planner-folder> && python3 tools/habits.py list                          # show habits + ids
cd ~/mnt/<planner-folder> && python3 tools/habits.py log --done sleep-bedtime,eat-morning   # log TODAY
cd ~/mnt/<planner-folder> && python3 tools/habits.py log --done eat-midday --date 2026-07-01
cd ~/mnt/<planner-folder> && python3 tools/habits.py status --days 7                # streaks + recent marks
cd ~/mnt/<planner-folder> && python3 tools/habits.py week --date 2026-07-01         # 7-day grid
```

A `log` records the **whole day**: ids you pass are done (✓); every other habit
is counted as missed (✗) for that date. So log once, at the end of the day, with
everything you actually did.

## Daily check-in flow

1. Show the habit list (or the areas the user cares about) and ask which they did
   today — sleep, eating, and each commitment.
2. Run `habits.py log --done <ids>` for today.
3. Show the returned streak view; call out streaks worth protecting and any habit
   slipping (low 30-day %). Keep it encouraging, not judgy.

## Weekly review

Run `habits.py week` (and `status`) at the end of the week: read the grid, name
the wins (longest streaks, best-kept area), pick **one** habit to focus on next
week. Tie environment tweaks back to the Eating-strategies / Sleep pages.

## Fits with other skills

- **eod-shutdown** is the natural place to run the daily check-in — add a
  "log today's habits" step there.
- Reviewing commitments here pairs with a periodic commitments check-in.

## Running this on a schedule

Create it with `create_trigger` (`update_trigger` to change one, `list_triggers` to
see what's already set). Three things decide whether a firing actually does anything:

- **Cron is evaluated in UTC**, not local time. Convert first. America/Lisbon is
  UTC−6 year-round, so 21:00 daily is `0 3 * * *`.
- **Pass `requires_local_device: true`** and name the planner folder. Each firing
  starts a fresh session in the cloud; without this it can't reach `tools/` at all and
  will quietly accomplish nothing.
- **Approvals stop an unattended run.** If the task isn't set to approve
  automatically, the firing halts at the first prompt with nobody there. Say this when
  you create it, and point at the task's own settings.

Each firing starts fresh with no memory of this conversation, so the prompt has to
carry everything — the folder, the date rule, the skill to follow, the exact commands,
and that it must not wait for input:

> Run the habit check-in for the ADHD planner. Work in the connected planner folder;
> every command is `cd ~/mnt/<planner-folder> && …`. Use today's date in the timezone
> from `tools/calendars.json`. 1) `cd ~/mnt/<planner-folder> && python3 tools/habits.py list`. 2) Ask which sleep /
> eating / commitment habits were done today; if nobody answers, log nothing rather
> than guessing and say so. 3) `cd ~/mnt/<planner-folder> && python3 tools/habits.py log --done <ids>`, then show
> the streak view. 4) On Sundays also run `cd ~/mnt/<planner-folder> && python3 tools/habits.py week` and give a
> short review naming one focus habit for next week. Follow the planner:habit-tracker
> skill. Self-contained; don't wait for input.

Confirm the time with the user before creating it. Nothing is scheduled unless they ask.
