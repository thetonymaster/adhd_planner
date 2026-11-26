# Zoom Out Review (Stage 5, Initial): `docs/designs/week-month-notes.md`

**Reviewer:** egm-zoom-out (fresh context). **Range:** lines 1–681. **Standard:** EGM zoom-out-standard.
**Context read:** AGENTS.md, GLOSSARY.md, docs/designs/task-priority-ranked-hubs.md, plugins/tasks/skills/obsidian-vault/SKILL.md, plus the files the design names.

**Verdict:** Revise before proceeding. There are no Blockers, and the context is sufficient.

## Elephant notes (author-side triage)

Q's decisions recorded in the brief or during drafting are marked **[decided]**. Lines marked **verified** were checked against the code in the main session.

| # | Severity | Finding | Elephant note |
|---|---|---|---|
| 1 | Major | The opt-in rule contradicts itself: `plan` writes to vaults that have rows but no `Recurring.md` (L273 vs L275) | **Verified** at L273/L275. A real defect; fix it. |
| 2 | Major | Non-goal 4 says occurrences stay out of the pool, but `due` puts them in the pool | Real contradiction. Choose between (a) cutting `due` and (b) rewording the non-goal and amending the Pool entry in the glossary. |
| 3 | Major | The `added:` ledger is unneeded; populating occurrences when the note is created is enough | **[decided]** Q chose the ledger. The trade-off: a rule added mid-period is missed until the next period. Re-open only if Q wants. |
| 4 | Major | Month notes aren't justified by the Problem | **[decided]** Q chose "Slices 1–3 in full" and said monthly items live only in month notes. The fix that is still worth making: add the user need to The Problem. |
| 5 | Major | The `fcntl.flock` lock isn't justified | Plausible. The race needs a stated scenario, or the lock goes. |
| 6 | Major | Finding a note by its `period:` frontmatter or detecting conflict copies is over-engineered | Plausible. The design never shows a user who renames notes or hits sync conflicts. |
| 7 | Nit | `week_monday` has no caller | Drop it. |
| 8 | Major | The design leaves out `setup_check.py`'s `needed` list and the "eleven scripts" counts | **Verified:** `setup_check.py:49-51`, `setup/SKILL.md:63,66`, `planner/EGM.md:85`. A real omission; fix it. |
| 9 | Nit | `due` is named like a read but writes; there are three write paths | Goes away if `due` is cut (finding 2a). |
| 10 | Nit | Importing `parse_vaults` from the `task_queue.py` CLI couples its `sys.exit` behavior and its `Tasks/` requirement | Move the pure helpers to `planner_config.py`. |
| 11 | Nit | The `## Days` Base view is extra | Plausible. It also removes the one manual check that is still unverified. |
| 12 | Nit | The design cites decisions it never records (Q1, Q2, "agreed earlier") | Link `concepts_brief.md` or restate each decision inline. |
| 13 | Nit | The habit tracker is missing from the Alternatives | Add a one-paragraph rejected alternative. |

---

## Findings (as reported)

### 1. Major: The opt-in rule contradicts itself. `plan` writes to vaults that never opted in.
- **Lines:** 273, 275, 168, 613
- **Evidence:**
  - L275: "Which vaults `ensure` touches. Only vaults that are in play and have a `Recurring.md` …"
  - L273: "Vaults written: every vault that has rows, and every vault that has a `Recurring.md`."
  - The L613 test implies that a vault with rows and no `Recurring.md` is written.
  - L168: "`plan` runs `ensure` again". But `ensure` skips vaults with no `Recurring.md`, so nothing says who creates their week note.
- **Proposed change:** One rule for every subcommand: a vault is written only if it has `Recurring.md`. Rows for other vaults stay in `tools/out` only. Add a test for "rows, no `Recurring.md` → not written".

### 2. Major: Non-goal 4 says occurrences stay out of the pool. The design then puts them in the pool.
- **Lines:** 62, 164, 287–296, 506
- **Evidence:**
  - L62: occurrences "don't enter the task pool".
  - L164: `due` "adds the open ones to the pool".
  - `GLOSSARY.md:22-24` defines Pool as the to-dos and the next work of task notes.
- **Simplicity:** `due` brings:
  - a third subcommand;
  - the `estimate_minutes` refactor;
  - a `source: recurring` row type;
  - a change to morning-startup's filter;
  - the needs-estimate path;
  - CUJ 3's plan-row link.

  Its only benefit is that recurring minutes come off a day's capacity.
- **Proposed change:**
  - **(a)** Cut `due` and move it to Future Improvements.
  - **(b)** Keep it, reword Non-goal 4 to "not in `task_queue.py`'s ranked list", and amend the glossary's Pool entry.

### 3. Major: The `added:` ledger is complexity the stated requirements don't need.
- **Lines:** 32, 49–50, 253–264, 456, 546, 611
- **Evidence:** Occurrences are frozen once written (L49). The ledger only matters when a rule is added mid-period to a note that already exists. Filling occurrences when the note is created, and never afterwards, gives the same guarantees with no state.
- **Cost:**
  - a frontmatter key users can damage;
  - the rebuild path, which still loses deletions;
  - a `set_added` rewriter;
  - an obsidian-vault rule;
  - a glossary term;
  - four tests;
  - Alternative F.
- **Proposed change:** Fill occurrences when the note is created. State the trade-off: a rule added mid-week first appears in next week's note. Drop the recurring markers and keep the `^id-period` block IDs.

### 4. Major: Month notes aren't justified by the Problem, and they bring most of the cross-note machinery.
- **Lines:** 14, 43, 82, 96–103, 132, 225–229, 277–279, 380–389, 444–445, 599–600
- **Evidence:** Problem 2 asks for a home for routines, not for a month-level note. These parts exist only because of month notes:
  - the Thursday rule;
  - `week_month` and `months_touched`;
  - the `month:` link;
  - the cross-note link;
  - CUJ 3;
  - Alternative H.
- **Simpler option:** A monthly occurrence is one checkbox in the week note whose dates contain it.
- **Proposed change:** Add a concrete need for month notes to The Problem, or cut them and move them to Future Improvements.

### 5. Major: The `fcntl.flock` lock solves a problem the design never shows it has.
- **Lines:** 299, 406, 461, 527, 617
- **Evidence:**
  - Writes are already atomic and `ensure` is idempotent.
  - The lock doesn't guard against the realistic concurrent writers, Obsidian and sync clients.
  - `fcntl` is POSIX-only.
  - It adds a dotfile in `Tasks/`, a side-effects entry, a context manager and a multi-process test.
- **Proposed change:** Drop the lock and keep the temp-file write followed by `os.replace`, or describe the race and the damage it would do in the NFRs.

### 6. Major: Identity resolution is over-engineered for renames and sync-conflict copies.
- **Lines:** 243–249, 455, 609
- **Evidence:** The frontmatter scan and the conflict-copy detection serve cases that no part of the Problem or the CUJs describes. The obsidian-vault rules already forbid renaming notes with `mv`.
- **Proposed change:** The note for period P is `Weekly/P.md`: use it if it exists, otherwise create it. Delete steps 2–3 and their tests.

### 7. Nit: `planner_config.py` helpers with no caller.
- **Lines:** 132, 441–445, 601
- **Proposed change:**
  - Drop `week_monday`, which only a round-trip test uses.
  - Keep `iso_week`.
  - Keep the month helpers only if month notes stay.

### 8. Major: The design leaves out `setup_check.py` and the setup skill's script counts.
- **Lines:** 436–659; the stale-tools guards at 505 and 517
- **Evidence:**
  - `setup_check.py:49-51` hard-codes the `needed` scripts.
  - `skills/setup/SKILL.md:63,66` says "eleven".
  - `plugins/planner/EGM.md:13,85` lists the scripts and the count.
  - The previous design updated all of these for `task_queue.py`.
  - As written, `planner:setup` would call a folder without `period_note.py` healthy.
- **Proposed change:**
  - Add `period_note.py` to `needed`, with a test in `tests/test_setup_check.py`.
  - Change eleven to twelve in the setup skill.
  - Extend file 8 to update `planner/EGM.md:13,85`.

### 9. Nit: `due` writes, and `plan` runs `ensure` again, which makes three write paths.
- **Lines:** 146–168, 164, 506
- **Proposed change:** If `due` stays, make it read-only and have the skill call `ensure` first.

### 10. Nit: Importing from a CLI module.
- **Lines:** 452
- **Evidence:** `task_queue.py:269-287`'s `parse_vaults` calls `sys.exit(2)` and requires `Tasks/`.
- **Proposed change:** Move `split_frontmatter`, `read_frontmatter` and `estimate_minutes` into `planner_config.py`. Keep `parse_vaults` in each tool, or state that `Tasks/` is part of eligibility.

### 11. Nit: The `## Days` Base view is extra.
- **Lines:** 218–224, 555, 678
- **Proposed change:** Leave it out of the template.

### 12. Nit: The design references decisions it never records.
- **Lines:** 70, 224, 334, 389, 398
- **Proposed change:** Restate each one inline or link `concepts_brief.md`.

### 13. Nit: The habit tracker isn't considered as a home for recurring items.
- **Lines:** 23, 328–398
- **Evidence:** `habits.py:1-13` and `habits.json:14-15` already track recurring commitments, but daily only and outside the vault.
- **Proposed change:** Add it as a rejected alternative.

## Scope note
The week note that holds the plan (Problem 1) is a small slice you can ship on its own: `plan` plus `ensure` plus the template plus the plan JSON. After that come recurring items with occurrences filled when the note is created, and then month notes, if a need is stated.
