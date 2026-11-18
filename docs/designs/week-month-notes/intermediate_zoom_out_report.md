# Intermediate Zoom Out (Stage 8): `docs/designs/week-month-notes.md`, lines 1–681

- **Reviewer:** egm-zoom-out, run in a fresh context.
- **Inputs:** the design and the reports from Stages 5, 6 and 7.
- **Standard:** zoom-out-standard.

**Verdict: Revise. Re-scope before fixing details.**

The three earlier stages produced 40+ findings. Applied as written, they would roughly double the normative text in §3–§5. Most Blockers and Majors come from two mechanisms the root problem doesn't need:
- the tool-rendered, JSON-routed plan section;
- `due`, which feeds recurring items into the pool.

## Elephant notes (author-side triage)

| # | Severity | Finding | Elephant note |
|---|---|---|---|
| 1 | Blocker | The skill writes the plan section with Edit, the way it writes the Daily `## Plan`. This deletes `period_note.py plan`, the plan JSON, `render_plan` and the routing. | **Verified precedent:** `morning-startup/SKILL.md:131` already titles rows `<vault>:<slug>: <item>`, and L163–169 writes each vault's blocks under `## Plan`, replacing them on a re-run. This closes C1, B2 and C4. **Counter-argument:** the brief's Blocker 4 wanted the rules in a tested tool. That still holds for the recurring section, where user state is merged. It is weak for a section that is replaced whole. The residual risk: the model could damage a marker. The tool's marker check on the next `ensure` catches that. |
| 2 | Major | Cut `due`. Recurring minutes come off capacity later (Future Improvements). | Removes the contradiction with Non-Goal 4 and about 12 findings. Cost: recurring items don't reduce the week's capacity. |
| 3 | Major | Identity is the canonical filename only. Drop the `flock` lock and the mtime re-check, and add one Risks line. | With canonical names only, a Skipped month note still exists, so "`month:` is always valid" holds. |
| 4 | Major | Built-in template text only, and no Base views. | Removes the rule that two template copies must stay identical, the placeholder rules and the unverified Base render check. Vault-editable templates move to Future Improvements. |
| 5 | Major | Smaller first slice: `ensure` only, plus a plan section the skill writes. | Keeps every decision you made: the ledger, month notes, `Recurring.md`, ISO weeks, notes per vault, and interactive-only writes. |
| 6 | Major | One opt-in rule: a vault takes part only if it has `Recurring.md`. | Closes Stage 5 #1, B1 and C2. |
| 7 | Nit | Bound the ledger. Lowercase the period in IDs (`2026-w48`), read both list forms, count `^ID` only inside the markers. | Small, and it closes C10, M6 and N11. |
| 8 | Nit | Drop `week_monday` and add the monthly need to The Problem. | Keeps the month helpers. |
| 9 | Nit | Fix the real gaps as stated: C6 setup plumbing, C5 CUJ grammar, M5 (skip with reason `no planner markers`), sources and terms. | Agreed. |

## Root causes (from the reviewer)

- **R1. The tool owns a multi-vault plan render.**
  - Findings: C1, B2, C4, the "rows" trigger at L273, M3 (plan outputs), N4, N5, N8, and the CUJ 3 plan link.
- **R2. Occurrences enter the pool through `due`.**
  - Findings: B3, M1, M2/C14, N6, N7, Stage 5 #2 and #9.
  - Nits: timezone, `--out F`, meeting capacity, stale `week-tasks`, the estimate in the middle of the line.
- **R3. Defences against scenarios no CUJ shows.**
  - The scenarios: renames, sync-conflict copies, concurrent runs.
  - Findings: M4, C3, C7, N9, Stage 5 #5 and #6.
- **R4. Two copies of the templates, plus Base views.**
  - Findings: M7, M8, C11, M10 (copying templates), Stage 5 #11.
- **R5. Two triggers for writing a vault.**
  - Findings: Stage 5 #1, B1, C2.

**Real gaps that are not over-design:**
- C6/M9 (setup);
- C5 (examples);
- C10/M6 (ledger form);
- M5 (notes without markers);
- C12/C13 (sources and terms).

## Proposed first slice (finding 5)

1. **`period_note.py ensure --vault … --date D`.**
   - It creates the week note and the month notes for that week from built-in text, only in vaults that have `Recurring.md`.
   - It fills the recurring sections through the `added:` ledger.
   - The week note's `month:` follows the Thursday rule. One static line links every month the week touches, which covers CUJ 3.
2. **`plan-week` (interactive):**
   - runs `ensure` for the planned Monday;
   - writes each opted-in vault's rows between its plan-week markers with Edit, split by the `<vault>:` title label.
3. **`morning-startup` (interactive)** runs `ensure --date <today>`.
4. **Plumbing:**
   - `iso_week`, `week_month` and `months_touched` in `planner_config.py`;
   - `setup_check.py` and the "eleven → twelve" counts;
   - the EGM and glossary entries;
   - an `update-vaults` prompt before it seeds `Recurring.md`.

**Open point the reviewer didn't address:** date handoff. In this slice the skill passes the planned Monday to `ensure`. That is the date-from-another-tool's-output pattern that `plan-week/SKILL.md:156` forbids, and it is why `due` ran `ensure` internally. Two ways to resolve it:
- (a) `ensure` takes `--week-start`/`--include-weekend` and calls `plan_days()` itself, the same as `plan_week.py`;
- (b) the skill passes the `Now:` date and `ensure` works out "next week on Sat/Sun".

(a) matches the existing tools.

## Recommended resolution order

1. Re-scope to the slice above (finding 5).
2. The skill writes the plan section (finding 1).
3. Cut `due` (finding 2).
4. One opt-in rule (finding 6).
5. Canonical names, no lock, built-in templates, no Base views (findings 3 and 4).
6. Fix the real gaps: C6, C5, M5 and the terms (finding 9).
7. Ledger IDs and list forms; drop `week_monday` (findings 7 and 8).
8. Last, the precision items for the smaller tool: the error table, the title formats, the recurrence regex, line endings.

Stage 9 (Implementation Readiness) on the current DetailedRange would mostly review sections that this re-scope deletes. That includes files 2a, 3, the `plan`/`due` parts of 6, 7, 11, 18 and 19.

---

# Stage 8 re-audit (after re-scope)

**Reviewer:** egm-zoom-out, run in a fresh context. **Verdict:** ready for Stage 9 once M1 and M2 are fixed. Every finding from the earlier stages is resolved or no longer applies. The scope fits the root problem.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| M1 | Major | CUJ 5 ("still writes the Plan section") contradicts §3 (only vaults reported as Wrote/Unchanged get a Plan section) | **Fixed.** The trigger is now "every vault not reported as `Off`". The data flow, §3 and file 6 are aligned. File 6 now says how exit 1 and exit 2 are handled. |
| M2 | Major | The Plan-section rules exist only in the design, which the skill can't read at runtime. The token-cost line understated the change. | **Fixed.** File 6 writes the rules into the skill as text. A `PlanWeekTest` assertion pins them. The token-cost line now gives the real size. |
| M3 | Major | `month:` and the Thursday rule no longer have a code consumer | **Contested; kept.** The Thursday link was your decision. The design now says in one line why the key exists (a queryable parent-month property) and that no code reads it. |
| N1 | Nit | The plan-week marker warning would fire on every month note | **Fixed.** It applies to week notes only, and a test covers it. |
| N2 | Nit | The "assigned" capacity figure counts every vault's rows | **Fixed.** Capacity figures are dropped from the Plan section. |
| N3 | Nit | `plugins/planner/README.md` and the Side Effects/Verification lists in `tools/EGM.md` were missing | **Fixed.** Added file 5a, and extended file 4. |
| N4 | Nit | The plan-week stale-tools guard stops users who never opted in | **Kept, with the reason stated:** one setup run refreshes every tool. |
| N5 | Nit | The glossary was getting implementation terms | **Fixed.** Mechanism terms go only in `plugins/EGM.md`. |

The re-audit cap (1) for Stage 8 is now used.
