# Project tasks pane: switch to another task of this repo from a click

Date: 2026-10-29. Status: draft for Q's approval.

## Why

The `/task` pane shows the one task this session is on. When Q works in a repo that has several task notes (wedding_bot: 2 active, 11 parked today), the others are invisible unless Q remembers their slugs. Q wants a second pane listing this repo's tasks, so picking up a parked one is a click, not a recall.

## Goals

- A separate pane, **project-tasks**, in the task-track mod, listing the non-`done` task notes of the repo this session runs in.
- Clicking a task puts `/tasks:task-switch <slug>` in the chat box. Q presses Enter. Nothing is sent by the click.
- A `+ New task` button puts `/tasks:task-start ` (trailing space, cursor at the end) in the chat box.
- Works on both surfaces Q uses: the terminal CLI and the desktop app.

## Non-goals

- No status changes, writes to notes, or skill runs from the pane. It only fills the chat box.
- No cross-vault list: only the vault this session resolved to.
- No placement control. The surface seats the pane (terminal: docked beside the transcript from 110 columns in fullscreen, else inline above the prompt; desktop: wherever the app puts panes). The mod API has no "session rail" or sidebar slot; checked against the 2.1.309 types (`placement` is read-only, `dock | inline`).
- Not the vault-wide `/board` from `2026-10-29-task-board-design.md`. That spec is separate and comes later.

## Anti-goals

- A click that sends a prompt without Q's Enter.
- A click that wipes text Q had typed in the chat box.
- A second source of truth: the list is read from the notes' frontmatter every time, never cached to a file.

## What Q sees

Option A from the mockups, with titles (`.superpowers/brainstorm/91481-1793312105/content/tasks-pane-layout-v2.html`):

```
Tasks · personal · wedding_bot
────────────────────────────────────
ACTIVE (2)
▸ Audit unbilled nil event_id calls
  Office re-enrich double charge
PARKED (11)
  Boundary error tuples (Pitfall 1)
  Decide: encrypt google_tokens
  …
  … 6 more
[ + New task ]
```

- **Header / pane title:** `Tasks · <vault name> · <repo name>`. Vault name only when `vaults.json` lists more than one vault (same rule as the `/task` pane's title, `vaultName` atom). Repo name = last path segment of the matched `repo:` root.
- **Rows:** the note's first `# ` heading; fall back to the slug when there is none (all 25 notes in the personal vault have one today).
- **Groups:** ACTIVE (`status: active`) then PARKED (`status: parked`), each headed with its count. Every other non-`done` status (empty, typos) goes under PARKED. *(Our call: never hide a task because of a bad status value.)*
- **Order within a group:** most recently modified note first (mtime).
- **Cap:** every Active task; the 5 most recent Parked tasks, then `… N more`. Pressing `… N more` expands the full Parked list for this session; the expanded list ends with a `Show less` row. *(The number 5 is Q-approved; `Show less` is our call.)*
- **This session's task** (the `task` atom's slug, same resolution as `/task`) gets the `▸` mark and the highlight, in whichever group it sits. Pressing it does nothing.
- **Empty:** no note in this vault matches the cwd → body says `No tasks for <cwd basename> in <vault>.` and still shows `+ New task`.

## Which notes are "this repo's"

A note belongs to the list when its `repo:` (normalized with `normalize()` from `resolve.ts`) is the session's root (`$.session.root()`) or a parent of it, and its status is not `done`. Same matching rule `pickTask` uses for the repo step, without the ranking.

When matches come from roots of different depth (a note on `~/personal` and another on `~/personal/wedding_bot`, session in wedding_bot), show only the deepest root's notes. *(Our call: the pane is about one project; the header names one repo.)*

## Opening it

- **Command:** `/project-tasks`, registered in the `COMMANDS` list like the others (no model turn). Opens and focuses the pane, replies `Project tasks: <repo name>` (or the empty-state line).
- **Band button:** `Tasks` next to the existing `Task` button on the band. The band only renders while a task is active, so the command is the way in otherwise.
- Pane id: its own constant (e.g. `task-track-project`), distinct from `PANE`.

## Clicking a row or New task

1. `$.prompt.read()`. If the draft is not empty (after trim), do not touch it: `$.ui.toast('Chat box has a draft: clear it, then click again.')` and stop. *(Our call, from the anti-goal: never overwrite typed text.)*
2. Else `$.prompt.fill({ text, mode: 'replace' })` with `/tasks:task-switch <slug>` or `/tasks:task-start `.
3. If the result has `isFilled: false`, toast why (`dialog` → "Close the dialog, then click again."; `no_composer` → "No chat box in this session."; absent → "Couldn't fill the chat box.") and leave the pane open.
4. On a successful fill, close the pane (`$.ui.close({ id })`) so the keyboard returns to the chat box and Q's next Enter sends the filled command. Never submit. *(Q decided. Why: a pane `Button` press leaves the keyboard with the pane, and Escape only hands it back; without the close, Enter would press the row again.)* The builder confirms in the test harness that after the close the prompt holds the keys; if a surface does not hand them back, say so in the plan rather than adding a submit.
5. Count the press as activity (`markActive($)`), like the `/task` pane's buttons do.

The slug sent is the note's file stem, which is what `task-switch` takes; the title only shows in the pane. When `vaults.json` lists more than one vault, the fill carries the vault prefix both skills accept: `/tasks:task-switch <vault>:<slug>` and `/tasks:task-start <vault>:`. *(Our call: the pane lists the mod's resolved vault, while a bare slug makes the skills look in the session-start `Vault:` first, so a same-named note in another vault could win.)*

## Freshness

The list re-reads on the mod's existing 15 s poll (`load()` every `POLL_MS`) and right after `/project-tasks` or the band button. A switch, park or new task made by a skill shows up within one poll. `candidates()` already lists every task note and caches frontmatter by mtime; the builder extends what it caches (title) rather than adding a second directory walk.

## Data and state

- Title: `Candidate` (`resolve.ts`) gains `title`, read alongside `repo`/`status` in `candidates()`. `Candidate` is used by the shared vault-resolution fixtures (`tests/fixtures/vault-cases.ts`); the field must be optional or the fixtures updated, and the Python side (`vaults.py`, `session_task.py`) is unaffected because resolution does not read it. *(Builder's call which.)*
- New `$.state` atoms, declared in `types/index.d.ts` under `task-track`: the list the pane draws (array of `{ slug, title, status, mtimeMs }` plus the repo name), and `isProjectMoreOpen: boolean` for the expanded Parked list.

## Versions, docs, checks

- Bump `plugins/task-track/.claude-plugin/plugin.json` 0.4.0 → 0.5.0.
- `plugins/task-track/README.md`: add the pane to the feature list and `/project-tasks` to the command table. `docs/setup.md` only if it lists task-track's commands.
- Add `.superpowers/brainstorm/` to `.gitignore` (mockups are scratch; currently untracked).
- Tests in `plugins/task-track/tests/task-track.test.ts`, run with `cd plugins/task-track && claude plugin test .`:
  - lists only this repo's non-done notes, Active then Parked, titles shown, slug fallback;
  - deepest-root rule;
  - cap at 5 Parked + `… N more`, expand and `Show less`;
  - session task highlighted, its press is a no-op;
  - row press with an empty draft fills `/tasks:task-switch <slug>` and closes the pane, never submits; with a draft it leaves the draft, toasts and keeps the pane open;
  - several vaults registered → fills carry `<vault>:`;
  - `+ New task` fills `/tasks:task-start `;
  - empty state.
- `claude plugin validate plugins/task-track`.

## Relation to the task-board spec

`2026-10-29-task-board-design.md` (untracked, not planned) will later shorten Active (new notes `parked`, SessionEnd parks) and drop the status tie-break in resolution. This pane reads `status:` as it stands and does not depend on either change; after the board lands, ACTIVE simply gets shorter. Both panes read titles from the same `candidates()` data, so whichever is built second reuses it.

## Left to the builder

- Colors and exact text widths; truncating long titles to the pane's `bodyColumns`.
- Keyboard handling inside the pane (whatever `Button` gives for free is enough).
- Optional vs required `title` on `Candidate`.
