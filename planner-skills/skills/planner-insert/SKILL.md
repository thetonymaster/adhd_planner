---
name: planner-insert
description: >
  Generate blank, print-ready A5 PDF inserts of the planner's template pages —
  priority matrix, brain dump, things-to-do, commitments, friend files, sleep,
  eating habits, weekly and monthly schedules, and more — to print and tuck into
  an A5 paper planner. Use when the user wants an empty page to fill by hand:
  "print a priority-matrix page", "a blank weekly insert", "give me the sleep
  page to print". For a daily page filled with real calendar events, use
  daily-page instead. Triggers: print a blank <page>, planner insert, printable
  priority matrix / sleep / weekly / monthly page, A5 insert to fill in.
---

# planner insert generator

Renders blank, fillable planner pages as A5 (or A6) PDFs styled to match an A5
paper planner: clean neutral palette, category tags, dot-grid boxes. Pure Python
+ reportlab, no other dependencies.

Run the commands below from the planner folder so the `tools/` path resolves. If
reportlab isn't installed yet: `pip install reportlab`.

## Steps

1. **Match the page.** If you're unsure which id the user's request maps to,
   list the options and pick the closest — e.g. "the eating page" → both
   `eating-strategies` and `eating-schedule`, so ask which (or make both):

   ```
   python3 tools/make_insert.py --list
   ```

2. **Generate.** One page (A5 by default):

   ```
   python3 tools/make_insert.py priority-matrix
   ```

   - Every page as one combined PDF: `python3 tools/make_insert.py all`
   - Smaller A6 to glue rather than tuck: `python3 tools/make_insert.py sleep-activities --size a6`

3. **Deliver the file.** The PDF lands in `tools/out/`. The file is the whole
   point, so always surface it with the present_files tool rather than only
   describing it. If the user asked for several pages, generate each and present
   them together (or use `all`).

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
