# task-track

Keeps the active Obsidian task note (the session's task: its /tasks:task-switch choice, else the note bound to its repo, else `Tasks/.active`) in view inside Claude Code, tracks Pomodoro focus, and writes to the note without a model turn.

## What it shows

- **Band above the prompt**, only while a task is active:
  `▶ set-up-vault  Next: Copy hooks (~10 min)  1/3 · ●○○○ 12/25m  [Done] [Task] [Tasks] [Hide]`
- **Status line**: `▶ set-up-vault 1/3 · ●○○○ 12/25m`
- **Pane** (`/task`): goal, Next as toggles, open loops, last 5 log lines, a note field, Park and Open in Obsidian.
- **Project tasks pane** (`/project-tasks`, or `Tasks` on the band): this repo's active and parked tasks by title (the 5 newest parked, `… N more` for the rest). A click fills the chat box with `/tasks:task-switch <slug>` (`+ New task`: `/tasks:task-start `) and closes the pane; you press Enter. It never sends, and leaves a typed draft alone.

## Commands (run mid-turn, no model turn)

| Command | Does |
|---|---|
| `/task` | Opens the pane. `/task hide` / `/task show` toggles the band. |
| `/project-tasks` | Opens the project tasks pane. |
| `/board [vault]` | Opens a read-only board of the vault's task notes: Doing · Parked · Done (finished in the last 7 days), grouped by project, this session's task marked `▸`. No argument: this session's vault. |
| `/note <text>` | Adds `- [[date]] HH:MM — text` to the Log |
| `/done [n]` | Checks off item n, or the first open one (again to reopen) |
| `/openloop <text>` | Adds an Open loop (`/loop` is a built-in) |
| `/pomo [start\|pause\|resume\|stop]` | Controls the shared Pomodoro; bare `/pomo` pauses or resumes |

Each one that writes to the note also adds a hidden one-line note so Claude knows what you logged (turn off with `notesToClaude`).

## Pomodoro (shared across sessions)

One timer for every Claude Code session, kept in `vault/Tasks/.pomo.json` (hidden from Obsidian, synced with the vault):

- **Timestamps, not counters.** Every session derives block progress from `now − blockStartedAt`, so two sessions never make a block fill twice as fast, and a restart picks up mid-block.
- **Activity is shared.** A prompt, press or command in any session updates `lastActiveAt` (at most once a minute). Claude's tool calls only keep a running block alive; they never start one. No activity anywhere for the short-break length mid-block ends the block; the next activity starts a fresh one.
- **One announcement.** 25 minutes into a block, the first session to tick bumps the count and announces it (toast + system notification). Others see it was announced and stay quiet.
- **Breaks are timed.** A finished block starts its break (`breakUntil`): 5 minutes, or 30 after every 4th block. The band shows `☕ ●○○○ break 4m left` / `☕ ●●●● long break 29m left`; no block starts and no focus is credited until it ends. The first prompt during a break says how long is left. The first activity after it starts the next block.
- **Controls.** `/pomo` pauses or resumes (and starts the timer when it is stopped or idle); `/pomo start|pause|resume|stop` for the rest. The band shows `⏸` (pause), `▶` (resume or start) and `⏹` (stop) for the current state. Pause freezes a block or a break; stop credits the time so far, logs it, and keeps activity from starting a block until `/pomo start` or the next day. Other sessions show a change on their next minute tick.
- **States at a glance.** `🍅 ●●○○ 12/25m` running · `⏸ … paused` · `☕ ●○○○ break 4m left` · `☕ ●●●● long break 29m left` · `⏹ off` · `○ ●●○○ idle`.
- **Break summary.** The break notification lists the Next items checked and the Log lines written during the block (`✓ … · 📝 2 notes: "…"`), or says nothing was. With `breakSummaryAI` on, a one-line Claude Haiku summary of the block follows.
- **Focus logged once.** Active time is credited once into today's per-task totals. On task switch or session end, the not-yet-logged part goes to the task Log and today's daily note — `focus 47m (2 pomodoros)` — and is marked logged so no other session repeats it. Finished days move to the plugin store (`focus:YYYY-MM-DD`; with 2+ vaults, `focus:<vault>:YYYY-MM-DD`).
- **Safe writes.** Written to a temp file and renamed over, so no session reads half a file; an unreadable file skips that round instead of resetting the timer.

## Several vaults

With `~/.config/adhd-planner/vaults.json` (see `docs/setup.md`), each session follows its own vault: the band and pane prefix `<vault> · ` (only with 2+ vaults), and each vault keeps its own timer in its `Tasks/.pomo.json`. A `/tasks:task-switch` to a task in another vault writes the old task's focus to its note first.

## Settings (`/config`, or `pluginConfigs["task-track@adhd-planner"].options` in settings.json)

| Field | Default |
|---|---|
| `vaultPath` | empty → `$VAULT`, else `~/vault`; ignored when a valid `vaults.json` loads; an absent, unreadable or invalid one falls back to it (the pane names the error) |
| `focusMinutes` / `breakMinutes` | 25 / 5 |
| `longBreakEvery` / `longBreakMinutes` | 4 / 30 |
| `staleEdits` | 10 edits by Claude since the Log changed → nudge (0 = off) |
| `notesToClaude` | true |
| `breakSummaryAI` | false. On: a one-line Haiku summary in the break notification; records your prompts (first 80 chars), edited files and commands during each block in `vault/Tasks/.pomo.json`, a synced file. About $0.0005 a break. |

## Install

See [docs/setup.md](../../docs/setup.md): `claude plugin install task-track@adhd-planner`. Claude Code only.

For development, point `CLAUDE_CODE_PLUGIN_DIRS` at this folder (`plugins/task-track`) instead; edits then reload the mod in running sessions.

## Develop

`claude plugin validate .` · `claude plugin test .`
