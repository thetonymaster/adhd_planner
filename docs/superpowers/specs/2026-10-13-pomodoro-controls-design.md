# Pomodoro controls: start, pause, resume, stop

Date: 2026-10-13 · Status: approved 2026-10-13 · Builds on the uncommitted timed-break work on `main` (`breakUntil`, `isLongBreak`, status line removed).

## Goal

Q always knows whether a block is running, paused, on break or off, without opening the pane, and can pause or stop the one shared timer, for example when stepping into a meeting.

## Decisions (from Q)

- **Hybrid model.** Activity still starts a block on its own, as today. Pause and stop override that until Q starts or resumes.
- **Indicator: the band above the prompt.** No status-line wrapper, no menu bar, no settings change, no new dependency.
- **Controls: `/pomo` plus band buttons.**
- **Stop lasts until `/pomo start` or the next day.** Otherwise the first keystroke would restart a block and stop would mean nothing.
- **Pause freezes whatever is running,** a block or a break.
- **The break notification summarizes the block from the task notes** (checked items, Log lines).
- **An AI one-liner is opt-in** (`breakSummaryAI`, off by default): Claude Haiku 5.5 over a short activity log kept in `.pomo.json`, not a fork of the session.

## States

One timer for the person, in `vault/Tasks/.pomo.json`, shared by every session.

| State | Entered by | Behaviour |
|---|---|---|
| running | activity (hybrid), `/pomo start`, `/pomo resume` | as today: a 25-min block, then a timed break |
| break | a block finishing | 5 min, or 30 after every 4th block; activity does not start a block |
| paused | `/pomo`, `/pomo pause` during a block or break | frozen: no credit, no completion, activity does not resume it |
| stopped | `/pomo stop` | the block ends and its time so far is credited; activity does not start a block until `/pomo start` or the day rolls over |
| idle | 5 min without activity mid-block, or a break ending | the next activity starts a block |

### File fields

Two new fields on `PomoFile`. Files written without them read as not paused and not stopped (the `emptyPomo` defaults in `parsePomo`), so no migration is needed.

- `pausedAt: number`: epoch ms the timer was paused; 0 = not paused.
- `isStopped: boolean`: Q stopped the timer; activity does not start a block.

### Transitions (pure, in `hooks/pomo.ts`)

Each takes `(f: PomoFile, now: number, cfg: PomoConfig)` and returns `{ file: PomoFile } | { error: string }`. An error names the current state, e.g. `Not paused (running 12/25m)`.

- `pause`: allowed while running or on break. Credits active time up to `now` (`credit`), sets `pausedAt = now`.
- `resume`: allowed while paused. Shifts `blockStartedAt` (when not 0) and `breakUntil` (when not 0) by `now - pausedAt`, sets `creditedUntil = now`, `lastActiveAt = now`, `pausedAt = 0`.
- `stop`: allowed in any state but stopped. Credits up to `now` when a block runs and is not paused (a paused block was credited at `pause`), then `blockStartedAt = 0`, `breakUntil = 0`, `pausedAt = 0`, `isStopped = true`.
- `start`: allowed while stopped, idle or on break (skips the rest of the break). Clears `isStopped`, `pausedAt`, `breakUntil`; starts a block at `now`. While running or paused: an error that says to use pause, resume or stop.
- `toggle` (`/pomo` alone): running or on break → `pause`; paused → `resume`; stopped or idle → `start`.

### Existing functions

- `touch`: while paused or stopped, returns the file unchanged. Activity neither resumes nor starts anything.
- `advance`: while paused or stopped, returns the file unchanged with no event.
- `shouldTouch`: false while paused or stopped, so no writes happen for nothing.
- `rollDay`: clears `isStopped` and `pausedAt` (a new day starts in hybrid).
- `isRunning`: false while paused or stopped.

## Indicator: the band

`pomoDots` becomes the one formatter used by the band and the pane:

- running: `🍅 ●●○○ 12/25m`
- paused: `⏸ ●●○○ 12/25m paused` (on break: `⏸ ●○○○ break 4m left paused`)
- break: `☕ ●○○○ break 4m left`; long: `☕ ●●●● long break 29m left`
- stopped: `⏹ off`
- idle: `○ ●●○○ idle` (replaces today's `break` label for an idle timer)

### Band buttons, by state

| State | Buttons |
|---|---|
| running, break | ⏸ Pause · ⏹ Stop |
| paused | ▶ Resume · ⏹ Stop |
| stopped, idle | ▶ Start |

They call the same transitions as `/pomo`, with no model turn, next to the existing Done / Task / Hide buttons.

### Several sessions

- The band and the task pane (opened with `/task` or [Task]) both show the timer. Each session has one pane; `/pomo` opens nothing.
- Every session draws the same shared timer. A button pressed in one session changes the file; other sessions show it on their next minute tick or activity, so up to about a minute later. The plugin API has no file watch (`$.fs` is read, write, stat, list, exists, ancestors), so this lag is accepted.
- Every transition reads the file fresh. A press that no longer fits (pause twice from two sessions) is a toast naming the state, e.g. `Already paused (12/25m)`.

## `/pomo` command

Declared next to `/note` with `immediate: true` and `argumentHint: '[start|pause|resume|stop]'`.

- No argument → `toggle`. `start|pause|resume|stop` → that transition.
- Anything else → toast `Unknown: /pomo <arg>. Use start|pause|resume|stop`. Nothing changes.
- Success → toast with the new state, e.g. `⏸ Paused at 12/25m on archive-cleanup`.
- `stop` then writes the task's unlogged focus to its Log and the daily note (`flushFocus`), as a task switch does.
- No active task → the same message the other commands give.

## Break summary

The notification at the end of a block says what the block got done, from the task notes. No model call.

```
Pomodoro 3 done on archive-cleanup · Break: 5 min
✓ Rewrite plan tasks 1–6 · 📝 2 notes: "D1 targeted plan ok", "key v1 added"
```

- **Checked items.** At block start, `.pomo.json` keeps a snapshot of the checked Next items of the task the block is on: `blockSnapshot: Record<slug, string[]>` (item titles). A task switched to mid-block gets its snapshot at the switch. At announcement, an item checked now and not in the snapshot counts. This catches checks from `/done`, the band, the pane and Claude editing the note.
- **Log lines.** Lines in each snapshotted task's `## Log` timestamped (`[[YYYY-MM-DD]] HH:MM`) at or after `blockOpenedAt`, the wall-clock start of the block. Pause does not shift it. The plugin's own `focus …` lines are left out.
- **Nothing found:** `Nothing checked or logged this block.`, as a nudge.
- **Length:** at most 3 items per kind, each cut to 40 characters, then `+N more`.
- **Where:** the toast and the system notification get the same text. The pure part (diff the snapshot, filter the Log, format) lives in `pomo.ts` / `note.ts`; `register.tsx` reads the notes.
- **A note that can't be read** at announcement is left out of the summary and named: `(couldn't read <slug>)`. The break still starts.
- **New fields:** `blockOpenedAt: number` (0 = no block) and `blockSnapshot`, set when a block starts, cleared when it ends or stops. Older files read as `0` / `{}`, which gives a summary with only the Log lines, filtered from `blockStartedAt`.

### AI one-liner (opt-in)

Setting `breakSummaryAI` (boolean, default `false`, in `plugin.json` options next to `notesToClaude`).

```
Pomodoro 3 done on archive-cleanup · Break: 5 min
✓ Rewrite plan tasks 1–6 · 📝 2 notes: "D1 targeted plan ok", "key v1 added"
Wrote the D2 archive scrub and its tests; plan for D1 checked.
```

- **Activity log.** Only while the setting is on and a block is running (not paused, stopped or on break), every session appends to `blockActivity: string[]` in `.pomo.json`:
  - `prompt: <first 80 characters>` on `prompt.submit`;
  - `edit: <path relative to the session root>` on `Edit` / `Write` / `NotebookEdit`;
  - `ran: <first 80 characters of the command>` on `Bash`.

  A repeat of the last entry is dropped. The list keeps the last 60 entries and is cleared when a block starts. Older files read as `[]`.
- **Privacy.** `.pomo.json` sits in the vault, so prompt and command text lands in a synced file. That's why the setting is off by default and nothing is recorded while it is off. The setting's description says so.
- **The call.** At announcement, the session that announces runs `$.model.complete({ model: 'claude-haiku-5-5', system, prompt, maxTokens: 120, effort: 'low', timeoutMs: 10000 })`.
  - The prompt holds the task slug, the note-based summary and the activity log.
  - The system prompt asks for one line under 120 characters saying what got done, with no preamble.
  - Cost: about 5k input tokens, roughly $0.0005 a break.
- **Order.** The break starts and the note-based toast shows at once. The AI line follows when the call answers, as a second toast and a system notification. The break never waits on it.
- **Failure.** No answer (`api-error`, `empty-reply`, `aborted`, timeout) → toast `(AI summary failed: <reason>)`. The note-based summary has already been shown.
- **Code layout.**
  - Pure, in `pomo.ts`: `recordActivity(f, entry)` (dedupe, cap) and `summaryPrompt(slug, noteSummary, activity)`.
  - `register.tsx`: the hooks and the call.

## Errors

- Transitions go through `changePomo` (read fresh, change, temp-file + rename).
- An unreadable `.pomo.json` makes the command say so and name the file. It never resets the timer.
- A transition that doesn't fit the state is a toast naming the state, not a silent no-op.

## Testing

Pure tests in `tests/task-track.test.ts`:

1. Pause during a block freezes progress and credit; resume after 10 min continues at the same minute.
2. Pause during a break freezes the countdown; resume continues it.
3. Activity while paused changes nothing; activity while stopped starts nothing.
4. Stop credits the time so far and ends the block; `start` starts a fresh block; the next day clears `isStopped`.
5. `start` during a break skips it; `start` while running is an error naming the state.
6. `toggle` from each state.
7. `pomoDots` for every state.
8. A file without the new fields parses as not paused, not stopped.

Plugin tests:

9. `/pomo`, `/pomo stop`, `/pomo resume` while not paused (error toast), `/pomo foo`.
10. `/pomo stop` writes unlogged focus to the task Log.
11. Band buttons match each state, and pressing ⏸ pauses the shared file.

Break summary:

12. Items checked during the block are listed; items checked before it are not; a task switched to mid-block is snapshotted at the switch.
13. Log lines before the block and `focus …` lines are left out; a pause does not drop lines written before it.
14. Nothing checked or logged gives the nudge; more than 3 gives `+N more`; long titles are cut to 40 characters.
15. An unreadable note is named and the break still starts.

AI one-liner:

16. Nothing is recorded while the setting is off, or while paused, stopped or on break.
17. Repeats are dropped, the list caps at 60, and it is cleared at block start.
18. With the setting on, a stubbed `model.complete` answer shows as a second toast after the note toast; a stubbed failure shows `(AI summary failed: api-error)`.
19. `summaryPrompt` includes the slug, the note summary and the log.

The 53 existing tests stay green; `claude plugin validate .` passes.

## Docs

- `README.md` Pomodoro section: the five states, `/pomo`, the band buttons.
- `.claude-plugin/plugin.json`: description drops "status line" (removed earlier) and mentions `/pomo`; new `breakSummaryAI` option.
- `README.md` settings table: `breakSummaryAI`, with the privacy note.

## Out of scope

- The status-line wrapper, the macOS menu bar, the terminal title.
- A "break over" notification.
- Forking the session for the summary (`$.model.fork`): considered, left out. It costs about $0.04–0.75 a break, and it only sees the announcing session.
- Per-session timers.
