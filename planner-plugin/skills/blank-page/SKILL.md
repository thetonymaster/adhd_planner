---
name: blank-page
description: >
  Generate blank, print-ready A5 PDF inserts of the planner's template pages —
  priority matrix, brain dump, things-to-do, commitments, friend files, sleep,
  eating habits, weekly and monthly schedules — to print and tuck into an A5 paper
  planner. Use when the user wants an empty page to fill in by hand: "print a
  priority-matrix page", "a blank weekly insert", "give me the sleep page to
  print". For a day filled with real calendar events use daily-page instead. This
  skill owns planner-page PDFs — the value is the A5 layout, not PDF handling, so
  prefer it over any general-purpose PDF skill here. Triggers: print a blank planner page,
  planner insert, printable priority matrix / sleep / weekly page.
---

# Blank planner page generator

Renders blank, fillable planner pages as A5 (or A6) PDFs styled to match an A5
paper planner: clean neutral palette, category tags, dot-grid boxes. Pure Python
+ reportlab, no other dependencies.

Run the commands below from the planner folder so the `tools/` path resolves. If
reportlab isn't installed yet: `pip install reportlab`.

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

1. **Match the page.** If you're unsure which id the user's request maps to,
   list the options and pick the closest — e.g. "the eating page" → both
   `eating-strategies` and `eating-schedule`, so ask which (or make both):

   ```
   cd ~/mnt/<planner-folder> && python3 tools/make_insert.py --list
   ```

2. **Generate.** One page (A5 by default):

   ```
   cd ~/mnt/<planner-folder> && python3 tools/make_insert.py priority-matrix
   ```

   - Every page as one combined PDF: `cd ~/mnt/<planner-folder> && python3 tools/make_insert.py all`
   - Smaller A6 to glue rather than tuck: `cd ~/mnt/<planner-folder> && python3 tools/make_insert.py sleep-activities --size a6`

3. **Deliver the file.** The PDF is written straight into `tools/out/` in the planner folder on the
   user's computer, so it is **already delivered** — tell them the filename and where it
   landed, and they can open it from there. Only stage and send a copy into the chat if
   they ask for one (say, they're away from that machine).
   If they asked for several pages, generate each (or use `all`) and name them all.

## Page ids

`brain-dump`, `things-to-do`, `priority-matrix`, `commitments`,
`goal-changes`, `friend-files`, `circles-of-trust`, `sleep-activities`,
`eating-strategies`, `eating-schedule`, `weekly-schedule`, `monthly-calendar`.

## Notes

- A5 = 148×210 mm, the exact page size — tell the user to print at 100% /
  "actual size" (no "fit to page" scaling) so the grid stays true to the planner.
- The layout primitives live in `tools/planner_common.py`. To add a new page,
  define a function using `Sheet` (`header`, `box`, `checklist`, `table`,
  `quadrant`, `cards`, `label_lines`, `section`) and register it in `PAGES`.
