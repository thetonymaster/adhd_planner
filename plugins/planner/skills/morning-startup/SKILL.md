---
name: morning-startup
description: >
  Build the user's entire day from scratch: pull today's Google Calendar, set the
  Top 3, break the main task into subtasks, time-block everything around the real
  meetings, and print the A5 daily page. Chains break-down-task + plan-day +
  daily-page and produces actual files. Use for "plan my day", "good morning, set
  me up", "build my day", "get me ready for the day". Draw the line carefully: a
  read-only summary of what's already scheduled is a morning *brief* and belongs to
  the morning skill, and a work or pipeline briefing belongs to the sales daily
  briefing — this skill is the one that decides what the user will actually do and
  hands back a plan plus a printed page. To time-block a task list they already
  have, with no calendar pull and no printing, use plan-day.
---

# Morning startup

Chains the planner skills into one "ready for the day" routine.

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

## Steps

1. **Pull today's meetings.** Google Calendar `list_events` for today across the
   calendars that hold real commitments (the user's primary, plus family/personal
   if relevant). Save to `tools/out/busy.json`.

2. **Gather today's tasks.** In order of preference:
   - yesterday's `tools/out/tasks-<yesterday>.json` (from capture-triage), and/or
   - `cd ~/mnt/<planner-folder> && python3 tools/triage.py parse` on `inbox.md` — if there are fresh captures,
     triage them first (see capture-triage), producing `tools/out/tasks-<today>.json`.
   Confirm the **Top 3** for today with the user (or take the top do/schedule items).

3. **Break down the main task** if one is big/vague — run break-down-task to get
   subtasks. Save the day's tasks with subtasks to `tools/out/day-tasks-<today>.json`
   as `[{"title":..,"subtasks":[..]}]`.

4. **Time-block around meetings:**

   ```
   cd ~/mnt/<planner-folder> && python3 tools/plan_day.py --tasks tools/out/tasks-<today>.json \
       --busy tools/out/busy.json --date <today> --work 09:00-18:00 --lunch 14:00-15:00
   ```

   Read the timed checklist (`tools/out/plan-<today>.md`) back to the user.

5. **Print the daily page:**

   ```
   cd ~/mnt/<planner-folder> && python3 tools/make_daily.py --date <today> --events tools/out/busy.json \
       --tasks tools/out/day-tasks-<today>.json
   ```

   The PDF is written straight into `tools/out/` in the planner folder on the
   user's computer, so it is **already delivered** — tell them the filename and where it
   landed, and they can open it from there. Only stage and send a copy into the chat if
   they ask for one (say, they're away from that machine).

6. **Offer** to push the focus blocks to Google Calendar (propose-first, from
   `tools/out/gcal-events-<today>.json`), and to refresh the live dashboard if the
   user set one up. Don't auto-create events.

## Vault (optional)

If the user's Obsidian vault is reachable, use it alongside the planner files.
If it isn't, or the run is unattended (a scheduled firing), skip this section
without mentioning it: the planner works without it.

- **Find it once:** the session-start `Vault:` line, else a connected folder named `vault` (`~/mnt/vault` in the
  device shell), else the `default` vault's `path` in `~/.config/adhd-planner/vaults.json`, else `$VAULT`, else `~/vault`, whichever the shell can see. Only that one vault is read or written, even when several are registered. It
  counts only if it has `Tasks/` and `Daily/`. Use the path you found on every
  command: `cd "<vault-path>" && …`.
- **Date:** the daily note's date is the device's local date
  (`date +%F` in the device shell), the same one the hooks use.
- **Rules:** follow the `obsidian-vault` skill when it's available. Either way:
  write only in the sections named below, add lines at the end of a section,
  never delete lines in `## Log` or `## Open loops` (strike through instead),
  never `mv` a note, and never create a `[[link]]` to a note that doesn't exist.
- **Daily note** is `Daily/<date>.md`. If it's missing, create it from
  `Templates/Daily.md`, replacing `{{date}}` and `{{title}}` with the date. If
  a section named below is missing, create it just above `## Log` (at the end
  if there's no `## Log`).
- **Task notes** are `Tasks/<slug>.md`; `Tasks/.active` holds the active slug.
  Open Next items are the unchecked `- [ ]` lines with text under `## Next`
  (skip empty placeholders). A trailing `(~N min)` is the item's estimate: take
  it as the minutes and drop it from the title. When an item goes into the
  planner, title it `<slug>: <item>` so later steps can tell it came from a
  task note.

In this skill:

- **Step 2, candidates for the Top 3:** add the open Next items of the active
  task (and of any task note the user names) to the pool, titled
  `<slug>: <item>`. Prefer them over generic inbox items when the user is
  mid-task.
- **Step 3:** break-down-task writes the subtasks into the task note; don't
  write them again here.
- **After step 4:** in today's daily note, write the confirmed Top 3 under
  `## Top 3`. It may already hold last night's picks from eod-shutdown: keep
  the ones still in today's Top 3 and replace the rest with today's picks,
  saying what changed. Write the timed checklist under `## Plan`, creating that
  section above `## Brain dump` if it isn't there. `## Plan` is generated, so
  replacing its contents on a re-run is fine; leave every other section alone.

## Preferences

Work 09:00–18:00, lunch 14:00–15:00 protected. Pomodoro 25/5, 30-min long break
after 4 sessions. Timezone comes from `tools/calendars.json` — read it, don't assume. Calendar changes are propose-first.

## Running this on a schedule

Create it with `create_trigger` (`update_trigger` to change one, `list_triggers` to
see what's already set). Three things decide whether a firing actually does anything:

- **Cron is evaluated in UTC**, not local time. Convert first. America/Lisbon is
  UTC−6 year-round, so 08:30 on weekdays is `30 14 * * 1-5`.
- **Pass `requires_local_device: true`** and name the planner folder. Each firing
  starts a fresh session in the cloud; without this it can't reach `tools/` at all and
  will quietly accomplish nothing.
- **Approvals stop an unattended run.** If the task isn't set to approve
  automatically, the firing halts at the first prompt with nobody there. Say this when
  you create it, and point at the task's own settings.

Each firing starts fresh with no memory of this conversation, so the prompt has to
carry everything — the folder, the date rule, the skill to follow, the exact commands,
and that it must not wait for input:

> Run morning startup for the ADHD planner. Work in the connected planner folder;
> every command is `cd ~/mnt/<planner-folder> && …`. Use today's date in the timezone
> from `tools/calendars.json`. 1) Google Calendar list_events for today across the
> calendars in `tools/calendars.json` → `tools/out/busy.json`. 2) Get today's tasks
> from `tools/out/tasks-<today>.json`, or parse and triage `inbox.md` if there are new
> captures. 3) Break any big task into subtasks → `tools/out/day-tasks-<today>.json`.
> 4) `cd ~/mnt/<planner-folder> && python3 tools/plan_day.py --tasks tools/out/tasks-<today>.json --busy
> tools/out/busy.json --date <today> --work 09:00-18:00 --lunch 14:00-15:00`.
> 5) `cd ~/mnt/<planner-folder> && python3 tools/make_daily.py --date <today> --events tools/out/busy.json --tasks
> tools/out/day-tasks-<today>.json` and say where the PDF landed. 6) Post the timed
> checklist and Top 3; offer — don't run — pushing focus blocks to Calendar. Follow the
> planner:morning-startup skill. Self-contained; don't wait for input.

Confirm the time with the user before creating it. Nothing is scheduled unless they ask.
