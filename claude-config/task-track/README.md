# task-track

Keeps the active Obsidian task note (`~/vault/Tasks/<.active>.md`) in view inside Claude Code, tracks Pomodoro focus, and writes to the note without a model turn.

## What it shows

- **Band above the prompt**, only while a task is active:
  `▶ set-up-vault  Next: Copy hooks (~10 min)  1/3 · ●○○○ 12/25m  [Done] [Task] [Hide]`
- **Status line**: `▶ set-up-vault 1/3 · ●○○○ 12/25m`
- **Pane** (`/task`): goal, Next as toggles, open loops, last 5 log lines, a note field, Park and Open in Obsidian.

## Commands (run mid-turn, no model turn)

| Command | Does |
|---|---|
| `/task` | Opens the pane. `/task hide` / `/task show` toggles the band. |
| `/note <text>` | Adds `- [[date]] HH:MM — text` to the Log |
| `/done [n]` | Checks off item n, or the first open one (again to reopen) |
| `/openloop <text>` | Adds an Open loop (`/loop` is a built-in) |

Each also adds a hidden one-line note so Claude knows what you logged (turn off with `notesToClaude`).

## Pomodoro (shared across sessions)

One timer for every Claude Code session, kept in `vault/Tasks/.pomo.json` (hidden from Obsidian, synced with the vault):

- **Timestamps, not counters.** Every session derives block progress from `now − blockStartedAt`, so two sessions never make a block fill twice as fast, and a restart picks up mid-block.
- **Activity is shared.** A prompt, tool call, press or command in any session updates `lastActiveAt` (at most once a minute). No activity anywhere for the short-break length = break taken; the next activity starts a fresh block.
- **One announcement.** 25 minutes into a block, the first session to tick bumps the count and announces it (toast + system notification). Others see it was announced and stay quiet. Every 4th block asks for the 30-minute long break.
- **Focus logged once.** Active time is credited once into today's per-task totals. On task switch or session end, the not-yet-logged part goes to the task Log and today's daily note — `focus 47m (2 pomodoros)` — and is marked logged so no other session repeats it. Finished days move to the plugin store (`focus:YYYY-MM-DD`).
- **Safe writes.** Written to a temp file and renamed over, so no session reads half a file; an unreadable file skips that round instead of resetting the timer.

## Settings (`/config`, or `pluginConfigs.task-track.options` in settings.json)

| Field | Default |
|---|---|
| `vaultPath` | empty → `$VAULT`, else `~/vault` |
| `focusMinutes` / `breakMinutes` | 25 / 5 |
| `longBreakEvery` / `longBreakMinutes` | 4 / 30 |
| `staleEdits` | 10 edits by Claude since the Log changed → nudge (0 = off) |
| `notesToClaude` | true |

## Install (local)

Add the folder to `~/.claude/settings.json` and start a new session:

```json
{ "env": { "CLAUDE_CODE_PLUGIN_DIRS": "~/personal/adhd_planner/claude-config/task-track" } }
```

Edits to the folder reload the mod in running sessions. With the mod on, drop the `SessionEnd` → `end-task.sh` hook: the mod writes the session's focus line itself.

## Develop

`claude plugin validate .` · `claude plugin test .`
