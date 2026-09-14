---
name: planner-insert
description: >
  Generate planner-Cousin-sized (A5) print-ready PDF inserts of the ADHD
  planner pages — priority matrix, brain dump, friend files, sleep, eating
  habits, weekly/monthly schedules, and more. Use when the user wants a paper
  insert to print and tuck into their planner Cousin, or asks for a printable
  version of a planner page. Triggers: planner, insert, printable planner
  page, A5 insert, print the priority matrix / sleep page / etc.
---

# planner insert generator

Renders blank, fillable planner pages as A5 (or A6) PDFs styled to match a
planner Cousin: clean neutral palette, category tags, dot-grid boxes.

## How to run

The generator is `tools/make_insert.py` in the adhd_planner project (pure
Python + reportlab, no other deps).

List available pages:

```
python3 tools/make_insert.py --list
```

Generate one page (A5 by default):

```
python3 tools/make_insert.py priority-matrix
```

Generate every page as one combined PDF:

```
python3 tools/make_insert.py all
```

Smaller A6 size (to glue rather than tuck):

```
python3 tools/make_insert.py sleep-activities --size a6
```

Output lands in `tools/out/`. After generating, share the PDF with the user
via the present_files tool.

## Page ids

`brain-dump`, `things-to-do`, `priority-matrix`, `commitments`,
`goal-changes`, `friend-files`, `circles-of-trust`, `sleep-activities`,
`eating-strategies`, `eating-schedule`, `weekly-schedule`, `monthly-calendar`.

## Notes

- A5 = 148×210 mm, the exact Cousin page size — print at 100% / "actual size",
  no scaling, so the grid stays true.
- The layout primitives live in `tools/planner_common.py`. To add a new page,
  define a function using `Sheet` (`header`, `box`, `checklist`, `table`,
  `quadrant`, `cards`, `label_lines`, `section`) and register it in `PAGES`.
