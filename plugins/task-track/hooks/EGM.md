# task-track hooks

## Overview

The Claude Code mod module of `task-track`. [hooks.json](./hooks.json) loads one
module, `register.tsx`, which owns every side effect (filesystem, store, UI, process,
prompt box, model calls). The other six files are pure functions over strings and plain
data: `register.tsx` gathers inputs and writes outputs (IO at the edge). Types for the
task view, the project list, the board target, the shared Pomodoro file and the plugin
state live in [../types/EGM.md](../types/EGM.md).

## Interface

- `register.tsx` — `export const register: Register`. Registers:
  - Lifecycle: `session.start` (registers commands, loads the task, polls every
    15 s, ticks the Pomodoro every 60 s), `session.end` (flushes unlogged focus; a
    failure is logged, never thrown).
  - `prompt.submit` (marks activity, reminds of a running break, records the prompt
    for the block), `tool.call` (keeps a running block alive, counts edits for the
    stale-Log nudge, reloads when the task note itself was edited).
  - Commands, run without a model turn: `/task [hide|show]`, `/board [vault]`,
    `/note <text>`, `/done [n]`, `/openloop <text>`, `/project-tasks`,
    `/pomo [start|pause|resume|stop]`.
  - UI: `ui.render` for `AbovePrompt` (the task band: slug, Next count, timer, pomo
    ⏸/▶/⏹, Done, Task, Tasks, Hide; the Next step on its own row) and three panes:
    `task-track` (the `/task` pane: Goal, Next toggles, Open loops, Log, note field,
    Park, Open in Obsidian), `task-track-project` (this repo's ACTIVE and PARKED
    tasks; a row or `+ New task` fills the chat box) and `task-track-board` (the
    read-only Doing / Parked / Done board of one vault).
- `resolve.ts` — vault and task resolution: `parseVaults`, `implicitVault`,
  `pickVault`, `pickTask` (test-only; skips `isSlug`), `defaultVault`, `frontmatter`,
  `field`, `FRONTMATTER`, `normalize`, `isSlug`, `taskNotePath`, `isZone`, `zoneFor`;
  types `Candidate` (optional `title`, for listing only), `Source`, `VaultSpec`,
  `VaultConfig`, `VaultState`, `VaultPick`.
- `project.ts` — the project-tasks list: `projectTasks(candidates, dir, home) ->
  ProjectList`, `visibleParked`, `PARKED_CAP` (5).
- `board.ts` — the task board: `boardNote`, `buildBoard(notes, today, days = 7)`,
  `boardHeader`, `fitColumn`; types `BoardNote`, `BoardColumn`, `BoardLine`.
- `note.ts` — task-note markdown: `parseNote -> TaskView`, `heading`, `sectionRange`,
  `insertInSection`, `toggleNext`, `firstOpen`, `progress`, `splitEstimate`,
  `logEntry`, `logOrder`, `codeSpans`, `stamp(date, timeZone)`, `elapsed`, `truncate`,
  `cells`, `fitCells`.
- `pomo.ts` — the shared Pomodoro state machine over `PomoFile`: `emptyPomo`,
  `parsePomo`, `serializePomo`, `rollDay`, `advance`, `touch`, `shouldTouch`,
  `start`, `pause`, `resume`, `stop`, `toggle`, `pomoState`, `onBreak`, `isRunning`,
  `blockMinutes`, `pomoDots`, `unlogged`, `markLogged`, `snapshotTask`,
  `recordActivity`, `recoverStaleClaims`, `TOUCH_EVERY_MS`, `MAX_ACTIVITY`,
  `CLAIM_STALE_MS`; types `PomoConfig`,
  `PomoEvent`, `PomoState`, `Transition`, `DayTotals`.
- `summary.ts` — what a finished block got done: `blockSummary`, `checkedTitles`,
  `logSince`, `summaryPrompt`, `SUMMARY_SYSTEM`; type `NoteRead`.

## Invariants

- **Shared contract with the tasks plugin.** `resolve.ts` mirrors
  [plugins/tasks/hooks/vaults.py](../../tasks/hooks/vaults.py) and
  [session_task.py](../../tasks/hooks/session_task.py): session override
  (`Tasks/.session/<id>`, newest) → non-`done` note named by a slug whose `repo:`
  holds the cwd (deepest, then newest, then slug; status other than `done` does not
  rank) → deepest vault `folders` entry → `default` vault's `Tasks/.active`. Both sides
  run `tests/fixtures/vault-cases.ts`; change them together. Known gap: `normalize`
  does no symlink resolution (resolve.ts:154) while `vaults.py` does, and
  `register.tsx` passes `$.session.root()` unresolved.
- A vault whose state can't be read is left out of resolution and named in the band's
  config error; it never stops the other vaults from loading. Within a vault, a task
  note that exists but can't be read fails that vault's resolution (as `vaults.py`
  does); the board instead shows what it can and names the unreadable notes.
- `note.ts`, `pomo.ts`, `summary.ts`, `resolve.ts`, `project.ts`, `board.ts` do no IO.
  Keep it that way; IO goes in `register.tsx`.
- Task-note frontmatter is cached by mtime (`noteCache` for resolution and the project
  list, `boardCache` for the board); a note is re-read only when its mtime moves.
- Project list: non-`done` slug notes whose `repo:` is the session root or a parent,
  deepest root only; active first, then newest; any status but `active` lists as parked.
  Shows every active task and the first `PARKED_CAP` parked ones, `… N more` for the
  rest. A row or `+ New task` press fills the chat box (`/tasks:task-switch
  [<vault>:]<slug>`, `/tasks:task-start [<vault>:]`, the vault prefix only with 2+
  vaults), never submits, never overwrites a draft, and closes the pane on success.
- Board: Doing = `active`, Parked = `parked`, Done = `done` with `finished` in the last
  7 days (today included, in the stamps' zone); other statuses are left off. Read-only:
  no control changes a status. The session's task is marked only on its own vault's
  board.
- Pomodoro uses timestamps, not counters: every session derives block progress from
  `now − blockStartedAt`, so sessions never double-count and a restart resumes
  mid-block. One session announces a finished block: the one whose write of
  `lastNotifiedBlock` / `notifiedBy` survives the read-back (the last writer).
  `/pomo` and the band's timer buttons read the file back too and report "Didn't
  stick" when another session overwrote the change.
- Activity: user prompts, presses and commands set `lastActiveAt`; Claude's tool calls
  also set it while a block runs (`tool.call` → `markActive($, true)` → `touch`), which
  keeps the block alive, but never start one. A `/pomo` prompt is not activity. Writes
  are throttled to once a minute except on a task change or when a block can start
  (`shouldTouch`).
- Focus is credited once per session (`creditedUntil`, `logged`); less than 5 minutes
  waits for the next flush. `flushFocus` claims before it writes, like the block
  announcer: it skips a slug that already has a claim (the holder writes it), else
  marks `logged[slug]` and sets `loggingBy[slug] = { by: SESSION, from, at }` only if
  the day and `logged[slug]` are still what it read and no claim landed, reads the
  file back, and writes the notes only if that claim is still there. Claims are per
  slug, so a claim on another task never cancels this one. A failed note write, or a
  read-back that finds the file unreadable, hands the claim back (`logged[slug]` =
  `from`) while it is still this session's; a successful write drops it.
- Claims never released (the session exited, the file stayed unreadable) are undone
  by `changePomo` through `recoverStaleClaims` once `CLAIM_STALE_MS` (2 min) old, before
  `rollDay`, so their focus is written later. `rollDay` waits while any claim is live,
  so a claim left just before midnight reaches the old day's notes once it is released
  or undone; focus credited in that wait (at most 2 min) counts toward the old day. Written twice
  instead of lost: a claim whose notes were written but whose release never landed,
  or whose holder stalled past 2 min (e.g. sleep mid-write) and then resumed; a
  timeout cannot fence a resumed holder's note writes. Known gap: two sessions that both read the file before either claim
  lands can both pass their read-back and both write; closing it needs a
  cross-session lock. `flushDay` (day rollover) has no per-slug claim yet, so two
  sessions rolling the day at once can log the same focus twice.
- Within one session, `flushFocus` runs one slug's flushes one after another (a
  per-slug promise queue, `flushing`), so overlapping triggers (`/pomo stop`, task
  switch, session end) never claim the same focus twice; each caller still gets its
  own flush's error.
- `.pomo.json` is never replaced when it exists but cannot be read or parsed this
  round; that round is skipped. A day or slug in it that can't name a note is reported
  (band problem + `$.ui.log`) and skipped, never thrown.
- Each command registers on its own: a refused name never blocks the others or the
  start hook.

## Side Effects

- Writes `<vault>/Tasks/.pomo.json` via a temp file named with `SESSION` (new on every
  module load) and `mv -f`; when `mv` fails, writes directly, logs once, and leaves the
  `.tmp` file behind.
- Writes the active task note (`/note`, `/done`, `/openloop`, pane toggles and note
  field, focus lines in `## Log`) and `<vault>/Daily/<date>.md` (`## Log` focus line;
  created from `Templates/Daily.md` or a minimal template when missing). The project
  and board panes write nothing.
- `$.store` keys `focus:YYYY-MM-DD` (one vault, or no config entry matches) or
  `focus:<vault>:YYYY-MM-DD`, written on day rollover (`saveDay`).
- Reads `vaults.json` (`$ADHD_PLANNER_VAULTS` or `~/.config/adhd-planner/vaults.json`),
  `$VAULT`, `$TZ`, every task note in each vault's `Tasks/`, `Tasks/.active`,
  `Tasks/.session/<id>`.
- UI: toasts, system notifications, `$.ui.log`, `$.ui.open` / `$.ui.close` for the
  panes; hidden context lines to Claude from the commands when `notesToClaude` is on;
  the `/task` pane's note field appends a user message with `$.session.append`; the
  project pane reads and fills the chat box (`$.prompt.read`, `$.prompt.fill`).
- With `breakSummaryAI` on: records prompts (first 80 chars), edited paths and Bash
  commands in `.pomo.json` (`blockActivity`, last 60) and calls `claude-haiku-5-5`
  for a one-line break summary.
- Runs `open obsidian://open?path=…` (pane button) and submits `/tasks:task-park`
  (Park button).

## Verification

- Run: `cd plugins/task-track && claude plugin test .`
- Run: `claude plugin validate plugins/task-track`
- Resolution changes: also `python3 -m unittest tests.test_vaults tests.test_load_task` (repo root).
