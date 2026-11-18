# Comprehension Test (Stage 6): `docs/designs/week-month-notes.md`

- **Reviewer:** egm-comprehension, run in a fresh context.
- **Ranges:**
  - FeatureRange: lines 1–423.
  - DetailedRange: lines 424–681.
- **Standard:** EGM re-implementation-standard.

**Verdict:** Not yet. An engineer could build the general shape from the document, but not identical code on the first try. Three Blockers stand in the way:
- the opt-in rule;
- the plan-section text, which is defined only by an example;
- the link and line format of an occurrence.

**Checks that passed:**
- Line references match the repo.
- The calendar facts are right: Nov 30 2026 falls in W49, 2026 has a W53, 2027-01-03 falls in 2026-W53, and 2024-12-30 falls in 2025-W01.
- The "from" versions match.

## Elephant notes (author-side triage)

**Verified** means the main session checked the claim against the file.

| # | Severity | Finding | Elephant note |
|---|---|---|---|
| B1 | Blocker | The opt-in rule contradicts itself for a vault with rows but no `Recurring.md`. The `month:` link can end up unresolved. | Same as Zoom Out #1, now confirmed by a second reviewer. **Verified** at L273/L275. Fix it. |
| B2 | Blocker | The plan-section text has no grammar, and the example mixes two weeks. | **Verified:** the L233–239 example has `### Mon Nov 23` and `### Mon Nov 30` in one section. Add the grammar and fix the example. |
| B3 | Blocker | The `link` of an occurrence is undefined for weekly rules, and the CUJ 1 line contradicts the format in §3. | **Verified:** L81 has no estimate and no date. Fix it. |
| M1 | Major | No contract for the `due --out` file. | Moot if `due` is cut (Zoom Out #2a). Otherwise, specify it. |
| M2 | Major | "rows marked `vault`" is ambiguous. `test_skill_files.py` pins the count of `"source": "vault"` strings. | **Verified:** `morning-startup/SKILL.md:57`. Reword it. |
| M3 | Major | The skip and warning strings are incomplete, CUJ output paths are missing `<vault>:`, and the exit code is described per vault. | Add a table of conditions and their messages. |
| M4 | Major | How sync-conflict copies interact with the identity steps is unstated. | Moot if identity is cut down to the canonical name only (Zoom Out #6). |
| M5 | Major | A note created by Periodic Notes, with no markers, is Skipped forever. | A real gap. Decide whether to append the sections or skip with a clear reason. |
| M6 | Major | Obsidian's Properties editor rewrites `added:` as a block list. | A real risk if the ledger stays. Read both forms and write the flow form. |
| M7 | Major | The Base view blocks are not written out. | Moot if the Days view is cut (Zoom Out #11). The Weeks view still needs its full text. |
| M8 | Major | The placeholder formats are underspecified: title across months and years, padding, month title. | Add the full template texts and the format rules. |
| M9 | Major | The stale-tools plumbing is missing: `setup_check.py`, the "eleven" counts, and the `tools/EGM.md` overview. | Same as Zoom Out #8, plus `tools/EGM.md:13–15`. Fix it. |
| M10 | Major | `update-vaults`: Goal 6 doesn't mention the prompt, "empty" is inaccurate, and dry-run and backup behaviour is not defined. | Reword it. |
| M11 | Major | The recurrence grammar has no regex and doesn't say whether fenced lines, `[x]` and dash variants are accepted. | Add a normative regex. |
| N1–N12 | Nit | See below. | N1 and N2 are the same as Zoom Out #12. N9 is moot if the lock is dropped. |

---

## Blockers

### B1. A vault with plan rows but no `Recurring.md`
- **Lines:** 225, 268–275, 613.
- **The conflict:**
  - L273: "every vault that has rows, and every vault that has a `Recurring.md`".
  - L275: `ensure` touches only opted-in vaults.
  - L225: "`month:` is always valid because `ensure` creates the month note".
- **What a reader can't decide:** for such a vault, should `plan`:
  - create `Weekly/`, which breaks the opt-in rule;
  - create the month note, which breaks the `ensure` scope;
  - or leave the `[[2026-11]]` link unresolved, which breaks the vault rule?
- **Proposed rewording:** `plan` writes only to vaults that have `Recurring.md`. For any other vault it prints `Skipped <vault>:Weekly/<W>.md: vault has no Recurring.md (not opted in)` and still exits 0. Change the L613 test to match.

### B2. The plan-section rendering exists only as an example
- **Lines:** 231–239, 266–273, 459.
- **Problem:** Goal 2 requires byte-identical output, but `render_plan` has no grammar, and the example contains headings from two different weeks. These are all unstated:
  - the day-heading format and locale;
  - the capacity text: whether "planned" means `usable` or the sum of assigned minutes, and where it goes;
  - the row grammar: whether the vault prefix is stripped, whether `(due …)` and `(overdue)` appear, the `→` arrow, and how a `link` is rendered;
  - the "Didn't fit" heading;
  - what an empty section looks like;
  - the blank lines and trailing newline.
- **Proposed addition:**
  ```text
  <section>  := (<day>)* [<overflow>]
  <day>      := "### " <Ddd> " " <Mmm> " " <D> "\n" [<cap>] <row>+
  <cap>      := "_Free " <h:mm> " · planning up to " <h:mm> "_\n"   (current vault only)
  <row>      := "- " <title-without-vault-prefix> " — " <minutes> "m" [" · " <prio>] [" (due " <date> ")"] [" (overdue)"] [" → [[" <link> "]]"] "\n"
  <overflow> := "### Didn't fit this week\n" <row>+
  ```
  Take the English day and month abbreviations from a fixed table, not from `strftime`. Fix the example so every heading falls in one week.

### B3. The weekly occurrence `link` and the CUJ 1 line format
- **Lines:** 81, 191, 236, 290–291, 103.
- **Problem:** The `due` JSON shows only the monthly link form. The plan example uses `[[#^…]]`. CUJ 1 L81 shows `- [ ] Weekly review ^weekly-review-2026-W48`, with no estimate and no date, which contradicts L191 and L215.
- **Proposed rewording:** `link` is `<note-basename>#^<id>-<period>`. `render_plan` writes `[[#^…]]` when the target is the week note being written. Change L81 to `- [ ] Weekly review (~30 min) — 2026-11-23 ^weekly-review-2026-W48`.

## Major

- **M1** (L287–296, 309, 506):
  - Define the `due --out` shape as `{"rows", "not_placed", "warnings"}`.
  - `title` and `minutes` come from the occurrence line via `estimate_minutes`.
  - stdout prints the `ensure` lines, then `Wrote <F>` last.
  - Use the same exit codes as `ensure`.
  - The skill shows `not_placed` the way it shows the queue's.
- **M2** (L296, 518):
  - Reword to "rows whose `source` is `"vault"`; the `vault` key plays no part in that filter".
  - Don't add a third `"source": "vault"` literal to morning-startup, because `test_skill_files.py` pins the count at two.
- **M3** (L83, 94, 121–122, 246–251, 302):
  - Add a table to §4 with each condition, its exact `Skipped … : <reason>` or `WARNING:` text, and its stream.
  - The CUJs should print `<vault>:<path>`.
  - Replace "exits non-zero for that vault" with "the process exits 1 after writing the other vaults".
- **M4** (L243–249): Use the regex `^<P>( \d+| \(conflict[^)]*\))\.md$`.
  - Conflict copies are excluded from step 2 and never written.
  - The tool warns when one is found.
  - If only copies exist, it creates the canonical note.
- **M5** (L65, 243–251, 263, 456): A note with zero markers needs one of two behaviours:
  - append both sections and add the frontmatter;
  - or skip it with the reason `no planner markers; add the sections from Templates/Weekly.md`, and update the Periodic Notes advice to match.
- **M6** (L253, 456):
  - Read `added:` either as a flow list or as a block list.
  - Always write it back as the one-line flow form.
  - Add a test for the block-list form.
- **M7** (L219, 229, 553–556):
  - Write both `base` blocks out in full, for example `file.name >= "{{monday}}" && file.name <= "{{sunday}}"`.
  - Add a manual Obsidian render check as step 0 of verification.
- **M8** (L207, 228–229, 463): Give the full template texts and a format rule for each placeholder:
  - a week spanning two months: `Nov 30 – Dec 6, 2026`;
  - a week spanning two years: `Dec 28, 2026 – Jan 3, 2027`;
  - week number padding;
  - the month title: `November 2026`;
  - the form of `{{month}}`.
- **M9** (L139, 505, 517, 650–655): Add these:
  - `period_note.py` to the `needed` list in `setup_check.py`, with a test;
  - eleven → twelve in `setup/SKILL.md` L63, 66 and 72;
  - the list and count in `planner/EGM.md`;
  - the `tools/EGM.md:13–15` overview, which currently says `task_queue.py` is the only tool that reads the vault.
- **M10** (L53, 408, 562, 570–575): `update-vaults` behaves like this:
  - it adds templates without a prompt;
  - it asks once per vault before adding the starter `Recurring.md`, and doesn't ask when the file exists;
  - `--dry-run` prints `Would add <path>`;
  - no backups are needed, because it only creates new files.

  Add tests for these cases.
- **M11** (L172–186): Add this normative regex:
  ```text
  ^- \[[ xX]\] (?P<text>.+?) — every: (?P<rule>.+?) #id/(?P<id>[a-z0-9][a-z0-9-]*)\s*$
  ```
  - Lines inside ``` fences are ignored.
  - Rule keywords are lowercase only.
  - `month N` requires 1 ≤ N ≤ 31.

## Nits

- **N1** (L70, 285, 185): Restate Q1 and Q2.
- **N2** (L224, 334, 389, 398): Some lines refer to decisions the reader never saw. Link the brief, or state each decision on its own.
- **N3**: Add a "Terms" list covering:
  - Base view, Cowork, in play;
  - the `Now:` line, the `Vault:` line;
  - `vault-allow.py`;
  - the board plugin, Periodic Notes, Templater;
  - current vault;
  - EGM.md.
- **N4** (L482): The "isn't renamed under `--keep-order`" line guards against nothing. Delete it or explain it.
- **N5** (L478): Say whether `weekly-plan-*.json` is always written. Give its key order, indentation and trailing newline.
- **N6** (L287, 506): Say whether weekend occurrences and past-day occurrences are dropped silently, or listed.
- **N7** (L506): Give the position of recurring rows relative to inbox and user items.
- **N8** (L269, 310):
  - An unknown `--current` exits 2.
  - A row naming a vault that wasn't passed is routed to `--current`, with a warning.
- **N9** (L299): Say whether the lock has a timeout or blocks forever.
- **N10** (L37): Say how CRLF line endings and a missing trailing newline are preserved.
- **N11** (L257–262): Say whether `^ID` is matched anywhere in the body or only inside the markers, and whether it must be the last token on the line.
- **N12** (L32): Point to the ledger table from "ticks and deletions survive".
