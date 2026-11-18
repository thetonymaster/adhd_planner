# Critic Review (Stage 7): `docs/designs/week-month-notes.md`, lines 1–423

**Reviewers:** egm-design, egm-structural, egm-style. Each ran in a fresh context. **Standard:** feature-spec-standard. The structural reviewer also used the design_doc template.

| Reviewer | Verdict |
|---|---|
| Design | Not ready: 1 Blocker, 8 Majors, 12 Nits |
| Structural | Revise: 0 Blockers, 3 Majors, 9 Nits |
| Style | Approve with revisions: 0 Blockers, 5 Majors, ~8 Nits |

**Verified** marks claims the main session checked against the code.

## Consolidated findings (deduplicated, ranked)

### 🔴 Blocker

**C1. Rows from vault tasks have no `vault` key, so multi-vault plans are written to the wrong vault.** (design B1) **Verified.**
- **Lines:** 133, 139, 267–273, 479–480.
- **The design's assumption:** `plan_week.py` copies `vault` "when the input had them" (L480), and a row without `vault` "goes to the current vault" (L269).
- **What the code does:** no input row has that key.
  - `task_queue.py:231-233` builds rows without a `vault` key. The vault appears only as the prefix of `task`, `vault:slug`, and only when there are several vaults.
  - `week_row` (`plan_week.py:174-178`) also drops everything but `title`, `minutes` and `source`.
- **What breaks:**
  - Every vault task lands in the current vault's week note, so CUJ 1 fails.
  - Non-Goal 3 is broken.
  - Work task titles leak into the personal vault.
- **Fix:** Add `"vault": <name>` to every `task_queue.py` row, even with a single vault. Remove `task_queue.py` from "Nothing else changes" (L139). Add a test with two vaults. (Deriving the vault from the `task` prefix is the alternative, but it fails in the single-vault case.)

### 🟡 Major

**C2. The opt-in signal is defeated or contradicted in two places.** (design M1, which joins Zoom Out #1 and Comprehension B1)
- **Lines:** 53, 225, 273, 275.
- **Problem:**
  - `update-vaults` seeds `Recurring.md` everywhere, which opts in every vault.
  - `plan` writes to vaults that have rows but no `Recurring.md`.
- **Fix:**
  - Vaults are written only when they have `Recurring.md`.
  - `update-vaults` asks before adding it.
  - Goal 6 is reworded to match.

**C3. "`month:` is always valid" is false.** (design M2)
- **Lines:** 225, 244–249.
- **Problem:**
  - When the month note is Skipped, the week note is left with a link to a note that doesn't exist.
  - A month note found by its `period:` key (because it was renamed) breaks the `[[2026-11]]` links.
- **Fix:**
  - Build links from the file name that was actually resolved.
  - State what happens to the week note when the month note is skipped.
  - Or simplify identity to the canonical filename only (Zoom Out #6), which removes the rename case.

**C4. The plan-JSON contract has no schema.** (design M4, and Comprehension B2)
- **Lines:** 133, 152–155, 271.
- **Problem:** The JSON passed between the two tools has no `format` version, no key table, and no rule for when it is written. "Planned capacity" is also not defined.
- **Fix:** Add a JSON example and a key table, in the task-priority design §4 style.

**C5. CUJ examples contradict the grammar and the estimate rule.** (design M8, Comprehension B3, and the two-Mondays example raised by all reviewers) **Verified.**
- **Lines:** 76, 81, 98, 101, 233–239, 290, 295.
- **Problems:**
  - The `Recurring.md` lines in the Givens lack `- [ ] `.
  - The occurrence lines lack the date.
  - Close books has no estimate but appears as 60m.
  - The plan example mixes W48 and W49.
- **Fix:** Write the CUJs in the exact grammar. Split the example into separate blocks for W48 and W49.

**C6. Old tools fail without a clear message.** (design M5, Zoom Out #8, Comprehension M9) **Verified.**
- **Problem:** `period_note.py` is missing from:
  - `setup_check.py:49-51`;
  - `setup/SKILL.md:63,66` ("eleven");
  - `planner/EGM.md:85`;
  - `tools/EGM.md:13–15`.
- **Fix:** Add it to all of these. `plan` should exit 2 with a clear message when the JSON is missing.

**C7. Concurrent writers (Obsidian and sync) are not covered.** (design M6, structural #1, Zoom Out #5)
- **Problem:** `flock` orders only `period_note.py` runs. An autosave from Obsidian or a sync client can lose edits between the read and `os.replace`.
- **Fix:** Re-check mtime and size before `os.replace`, and Skip if they changed. Then decide whether to drop the lock (Zoom Out #5). Fix the "planner's dotfiles" wording: `Tasks/` dotfiles belong to the tasks plugin.

**C8. The Risks & Mitigations section and Security & Privacy coverage are missing.** (structural #1, style M4)
- **Fix:** Add `### Risks and Mitigations` under NFRs, covering:
  - concurrent editors;
  - the Bash permission prompt;
  - sync-conflict copies;
  - loss of the ledger;
  - folder-scan growth.

  Add a Security & Privacy bullet saying which rule approves `python3 tools/period_note.py`. Replace the absolute claim "the only risk".

**C9. The alternative "skill writes the sections with Edit/Write" is missing.** (design M7)
- **Background:** Daily `## Plan` already uses this pattern (`morning-startup/SKILL.md:163-169`), and `vault-allow.py` approves Write/Edit but not Bash.
- **Fix:** Add it as Alternative J, rejected because the model's writes can't be unit-tested or reproduced. Add an NFR line on the Bash permission prompt.

**C10. The `added:` ledger in block-list form, and the ID character set.** (design M3, Comprehension M6)
- **Problem:**
  - Obsidian's Properties editor rewrites `added:` as a block list.
  - The IDs contain an upper-case `W`, but the character set is `[a-z0-9-]`.
- **Fix:** Read both forms and write the flow form. Correct the character set.

**C11. The Base blocks are written as placeholder prose.** (structural #3, Comprehension M7)
- **Lines:** 218–219, 229.
- **Fix:** Write out the full `base` blocks and add a manual render check in Obsidian. Or drop the Days view (Zoom Out #11).

**C12. Additional Resources is missing, and the design cites decisions that aren't recorded.** (structural #2, style M3, Zoom Out #12, Comprehension N1/N2)
- **Lines:** 70, 224, 275, 334, 362, 389, 398.
- **Fix:**
  - Add `### Additional Resources` with links to GLOSSARY.md, the three EGM.md files, the task-priority design, and the concepts brief (moved to `docs/designs/week-month-notes/`).
  - Replace each "you asked" or "agreed earlier" with the Goal or Non-Goal it rests on.
  - Spell out Q1 and Q2.

**C13. The same terms drift between names.** (style M1/M2, structural #11, design N12)
- **Problem:** "Occurrences section", "recurring section" and `## Recurring` are used for one thing, and so are "definition list" and "Recurrence list". "Period note" is missing from the glossary list.
- **Fix:** Define the **Plan section** and the **Recurring section** once at L30, and use the term "Recurrence list" throughout.

**C14. The `morning-startup` filter sentence is ambiguous.** (style M5, Comprehension M2) **Verified.**
- **Line:** 296. The real rule is at `morning-startup/SKILL.md:57`.
- **Fix:** Say "rows whose `source` is `"vault"`".
- **Correction:** the style reviewer's suggested rewrite ("drops rows whose `vault` differs") is wrong; don't use it.

### 🟢 Nits (grouped)

**Problem statement**
- L21–22: plans are kept for each week in `tools/out`. The real problem is that they are outside the vault (unsynced, unlinked, git-ignored). Reword it.

**Behaviour gaps**
- Weekend-dated occurrences and past-day occurrences disappear silently from `due`. List them.
- A meeting reminder that has an estimate takes away planned capacity, which contradicts Non-Goal 2.
- Recurring rows in `week-tasks-*.json` go stale, and `week_row` drops `vault`, so another vault's occurrence could land in the current Daily note.
- A text containing `<!-- planner:` would break the marker count. Reject or escape it.

**Interface and contract details**
- The output format is `Wrote <vault>:<path>`, but the CUJs drop the vault. The exit code is per process, not per vault.
- The stripping rule for plan-row titles (`vault:slug: item`) is not stated.
- The estimate sits mid-line in an occurrence line. Say how it is parsed.
- `due --out F` breaks the task-priority decision that tools allocate unique output files.
- The timezone: `due` and `plan` use `date.today()`, while `ensure` uses `Now:`. They can name different weeks near midnight.

**Formatting**
- Bold lead-ins in §3 and §4 should become `####` headings.
- Add the missing blank lines before lists.
- Make the stray ``` at L251 a code span.
- Fix the diagram's column collisions at L143–161.
- Use `<week-start>` consistently.
- Use repo-root paths in citations.

**Wording**
- Replace vague phrases: "too thin", "heaviest", "most skipped weeks", "harmless", "backup story".
- Add first-use glosses for Cowork, Base view and `plan_days`.

## How these relate to your earlier decisions

- **C1** is new and the most serious finding. No earlier stage caught it.
- **C2, C5 and C6** are now confirmed by three reviewers each.
- **C7** argues against Zoom Out #5's "just drop the lock". With or without the lock, the real risk is Obsidian, and the mtime re-check is what addresses it.
- None of these findings contests your decided items: the ledger, month notes, and slices 1–3.
