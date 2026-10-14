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

1. **Review today.** Load today's plan (`tools/out/plan-<today>.md` /
   `tasks-<today>.json`) and, for context, today's calendar via `list_events`.
   Ask the user (or, if unattended, list the planned tasks and mark none done):
   what got **done**, what **didn't**.

2. **Migrate unfinished** to tomorrow's inbox so nothing is lost:

   ```
   cd ~/mnt/<planner-folder> && python3 tools/triage.py carry --items tools/out/leftover.json
   ```

   where `leftover.json` is a JSON list of the undone task titles. They land in
   `inbox.md` for tomorrow's triage/morning-startup.

3. **Brain-dump to clear your head.** Invite any loose thoughts; append them to
   `inbox.md` (one `- ` line each).

4. **Triage the inbox** (capture-triage): `cd ~/mnt/<planner-folder> && python3 tools/triage.py parse`, classify
   into buckets + matrix, write `tools/out/decisions.json`, then
   `cd ~/mnt/<planner-folder> && python3 tools/triage.py apply --decisions tools/out/decisions.json --date <today>`.
   Keep **tomorrow's Today list light** — only what truly must happen.

5. **Wind-down / bedtime routine.** Walk the Sleep-page routine: bedroom set,
   hygiene, tomorrow prep (clothes, bag, keys). Optionally compute a bedtime by
   working backward from the wake time and offer to set a bedtime reminder
   (add-event, propose-first).

6. **Seed tomorrow.** Confirm tomorrow's **Top 3**. Then produce the requested
   outputs:
   - **Shutdown summary in chat** — done vs. undone, what was migrated, tomorrow's Top 3.
   - **Tomorrow's daily-page PDF.** Two files have to exist first: pull tomorrow's
     calendar into `tools/out/busy-tomorrow.json`, and write the Top 3 you just
     confirmed to `tools/out/day-tasks-<tomorrow>.json` as
     `[{"title":..,"subtasks":[..]}]`. Nothing else creates that second file, and
     without it the page renders with an empty task column — it warns on stderr now,
     but don't rely on noticing. Then run `make_daily.py` for `<tomorrow>` with both.
   - **Proposed focus blocks for tomorrow** — run `plan_day.py` for tomorrow and
     offer to push `gcal-events-<tomorrow>.json` to Calendar (propose-first).
   - **Refresh the dashboard** with tomorrow's Top 3 + tasks, if the user set up
     the optional live dashboard (skip otherwise).

## Vault (optional)

If the user's Obsidian vault is reachable, use it alongside the planner files.
If it isn't, or the run is unattended (a scheduled firing), skip this section
without mentioning it: the planner works without it.

- **Find it once:** a connected folder named `vault` (`~/mnt/vault` in the
  device shell), else `$VAULT`, else `~/vault`, whichever the shell can see. It
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

- **Step 1, evidence of the day:** read today's daily note `## Log` and the
  active task note's `## Log` and `## Next`. Use what's there (focus or session
  lines, if any tool wrote them) to suggest what got done instead of asking
  cold.
- **Step 2:** an unfinished item that came from a task note (titled
  `<slug>: …`) stays in that note's `## Next`. Don't also carry it to
  `inbox.md`, or it shows up twice.
- **Step 4:** the triage includes the vault inbox, as capture-triage
  describes.
- **Park the active task:** if `Tasks/.active` names a task, run `/tasks:task-park`
  when that skill is available. Otherwise check off the Next items the user
  confirmed done and add a `## Log` line; don't reorder or rewrite the rest.
- **Step 6:** write the shutdown summary (done, migrated, tomorrow's Top 3)
  under `## Shutdown` in today's daily note, creating it just above `## Log`.
  Write tomorrow's Top 3 under `## Top 3` in tomorrow's daily note, creating the
  note from the template if needed.

## Preferences

Work 09:00–18:00. Pomodoro 25/5, 30-min long break after 4. Timezone comes from `tools/calendars.json` — read it, don't assume. Calendar changes are propose-first. Keep tomorrow realistic.

## Running this on a schedule

Create it with `create_trigger` (`update_trigger` to change one, `list_triggers` to
see what's already set). Three things decide whether a firing actually does anything:

- **Cron is evaluated in UTC**, not local time. Convert first. America/Lisbon is
  UTC−6 year-round, so 18:00 daily is `0 0 * * *`.
- **Pass `requires_local_device: true`** and name the planner folder. Each firing
  starts a fresh session in the cloud; without this it can't reach `tools/` at all and
  will quietly accomplish nothing.
- **Approvals stop an unattended run.** If the task isn't set to approve
  automatically, the firing halts at the first prompt with nobody there. Say this when
  you create it, and point at the task's own settings.

Each firing starts fresh with no memory of this conversation, so the prompt has to
carry everything — the folder, the date rule, the skill to follow, the exact commands,
and that it must not wait for input:

> Run the EOD shutdown for the ADHD planner. Work in the connected planner folder;
> every command is `cd ~/mnt/<planner-folder> && …`. Today = current date in the
> timezone from `tools/calendars.json`, tomorrow = +1 day. 1) Review today's plan
> (`tools/out/plan-<today>.md`, `tasks-<today>.json`) and calendar. 2) Unattended, task
> completion is unknown — carry today's planned tasks forward, except titles of the
> form `<slug>: …` (they live in a vault task note already): write the titles
> to `tools/out/leftover.json` and run
> `cd ~/mnt/<planner-folder> && python3 tools/triage.py carry --items tools/out/leftover.json`. 3) Triage the inbox:
> `cd ~/mnt/<planner-folder> && python3 tools/triage.py parse`, classify, write `tools/out/decisions.json`, then
> `cd ~/mnt/<planner-folder> && python3 tools/triage.py apply --decisions tools/out/decisions.json --date <today>`.
> Keep tomorrow's Today list light. 4) Pull tomorrow's calendar to
> `tools/out/busy-tomorrow.json`, run `plan_day.py` for tomorrow (work 09:00-18:00,
> lunch 14:00-15:00), write the Top 3 to `tools/out/day-tasks-<tomorrow>.json`, then
> `make_daily.py` for tomorrow with both files. 5) Post the shutdown summary and say
> where the PDF landed. Offer — don't run — pushing tomorrow's focus blocks to
> Calendar. Don't read or write the Obsidian vault. Follow the planner:eod-shutdown
> skill. Self-contained; don't wait for input.

Confirm the time with the user before creating it. Nothing is scheduled unless they ask.
