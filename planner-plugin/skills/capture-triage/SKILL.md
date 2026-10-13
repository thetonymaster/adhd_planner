---
name: capture-triage
description: >
  Use whenever someone dumps out many mixed, unsorted items — to-dos, thoughts,
  worries, reminders, swirling in their head or jotted on a list — and wants help
  deciding what actually matters and what to do first. Take the whole jumble and
  hand back a prioritized plan: each item ranked by when (today / this week /
  later) and by priority (do now / schedule / hand off / drop), with rough time
  estimates. The go-to for "clear my head", "organize everything on my mind",
  "what should I actually work on", triaging a brain dump, sorting a raw list into
  a priority matrix. Not for tidying files, adding calendar events, summarizing
  text, or distilling research and interview notes into themes. To break one big
  task into steps use break-down-task; to time-block an already-sorted list use
  plan-day.
---

# Capture & triage

The intake front door: messy capture in, sorted plan out.

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

## Inputs

- **inbox.md** (repo root) — the user jots one thought per line (`- ...`) all day.
- **Live dump** — anything the user types now. Add those lines to inbox.md first
  (so they're archived too), or include them in the item list you classify.

## Steps

1. **Parse the inbox:**

   ```
   cd ~/mnt/<planner-folder> && python3 tools/triage.py parse
   ```

   Prints the raw items as JSON. If empty and there's no live dump, tell the
   user there's nothing to triage and stop.

2. **Classify every item** (this is your judgment). For each, decide:
   - **bucket**: `today` (must move today), `soon` (this week), `eventually`.
   - **quadrant**: `do` (important & urgent), `schedule` (important, not urgent),
     `delegate` (urgent, not important — a quick handoff/call), `delete` (drop /
     someday-maybe, low value).
   - **minutes**: a rough estimate for real tasks (pad ~25%). Round toward 25/50/75.
   - optional **note**: why it's urgent, a deadline, etc.

   ADHD guidance: be honest about what's actually *today* — cap Today at what
   fits the remaining hours. Push the rest to Soon. Actively mark low-value
   items `delete` so the list stays short.

3. **Write a decisions.json** (list of `{item, bucket, quadrant, minutes, note}`)
   to `tools/out/decisions.json`, then apply:

   ```
   cd ~/mnt/<planner-folder> && python3 tools/triage.py apply --decisions tools/out/decisions.json --date <today>
   ```

   This writes `triage-<date>.md` (summary + matrix), `tasks-<date>.json`
   (Today's do/schedule items, for plan-day), archives the inbox to
   `inbox-archive.md`, and clears inbox.md.

4. **Show the summary** in chat: the three buckets and the matrix, and call out
   what you dropped and why.

5. **Offer the next step** — hand `tasks-<date>.json` to the **plan-day** skill
   to time-block Today's items around the calendar, and/or the **daily-page**
   skill to print the page. Don't auto-run; ask.

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

- **Inputs:** before step 1, append the non-empty bullets from
  `00 Inbox/Inbox.md` to the planner's `inbox.md`, the same way as a live dump,
  so `triage.py apply` archives them in `inbox-archive.md`. Only after `apply`
  reports them archived, remove exactly those bullets from the vault inbox,
  leaving its heading, its empty `- ` placeholder and anything added since you
  read it.
- **Big items:** an item that's really a multi-step project gets the suggestion
  "make it a task note" (with `/task-start <name>` when that command exists)
  instead of a single estimate.
- **Log it:** add one line to today's daily note under `## Log`:
  `- HH:MM triage: <n> today, <n> soon, <n> dropped`.

## Scheduled run (daily 18:00)

A scheduled task runs this at end of workday. When triggered with no user
present: parse, classify, apply, and leave the summary + `tasks-<date>.json`
ready. Keep it self-contained — read inbox.md, don't wait for input. Leave the
vault alone: its inbox is triaged only when the user is there.
