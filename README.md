# ADHD Planner

ADHD-friendly planning for Claude Code and Cowork: dump everything out, sort it, break the big thing
into startable steps, time-block it around your real meetings, print an A5 page, and keep the task
you're on in view with Obsidian task notes.

This repo is a Claude plugin marketplace, `adhd-planner`, with three plugins:

| Plugin | What it does | Runs in |
|---|---|---|
| [`planner`](plugins/planner) | 12 skills: brain-dump triage, task breakdown, day and week planning around Google Calendar, A5 printable pages, habits with streaks, morning startup and end-of-day shutdown | Claude Code, Cowork |
| [`tasks`](plugins/tasks) | Obsidian task notes: start, park and switch tasks; the active task's Goal/Next/Open loops at session start; vault access without prompts | Claude Code, Cowork |
| [`task-track`](plugins/task-track) | A mod: task band and pane, one shared Pomodoro, `/note` `/done` `/openloop` `/pomo` without a model turn | Claude Code only |

## Install

Claude Code, with the interactive installer (needs [uv](https://docs.astral.sh/uv/)):

```bash
uvx --from "git+https://github.com/thetonymaster/adhd_planner#subdirectory=setup" planner-setup
```

Or by hand:

```bash
claude plugin marketplace add thetonymaster/adhd_planner
claude plugin install planner@adhd-planner
claude plugin install tasks@adhd-planner
claude plugin install task-track@adhd-planner
```

Then run `/planner:setup` in the folder you want to use as your planner. It copies the tools,
wires up your calendars and smoke-tests everything.

Cowork, vault paths, several vaults and permissions: [docs/setup.md](docs/setup.md).

## Try it

- "Clear my head: <everything on your mind>" → `capture-triage`
- "Break down <the big task>" → `break-down-task`
- "Plan my day" → `morning-startup`
- "Wrap up my day" → `eod-shutdown`
- `/tasks:task-start` in a repo, then `/pomo start` (with `task-track`)

## Requirements

- **planner**: Python 3.10+; `reportlab` for the printing skills; a Google Calendar connector for
  anything that touches your schedule.
- **tasks**: `python3` for the hooks; an Obsidian vault (`examples/vault-starter/` is a starting point).
- **task-track**: Claude Code.

## Repo layout

| Path | What |
|---|---|
| `plugins/` | The three plugins |
| `setup/` | `planner-setup`, the installer (uv project) |
| `examples/` | Starter vault, example `CLAUDE.md` and settings |
| `docs/` | Setup guide; specs and plans under `docs/superpowers/` |
| `*.html`, `app.js`, `styles.css` | The original fillable planner pages (open `index.html`) |
| `tools/`, `habits*.json`, `inbox.md` | The author's own running planner folder |

## Disclaimer

A productivity tool, not medical advice; not affiliated with any planner brand. ADHD
is a medical condition: talk to a clinician about diagnosis and treatment.

Licensed under [MIT](LICENSE). Security notes: [SECURITY.md](SECURITY.md).

## Contributing

Checks, layout details and conventions are in [AGENTS.md](AGENTS.md). In short: run the test suite
for what you touched, bump the plugin's `version` when it changes, and rebuild `planner.plugin` with
`bash scripts/build-plugin.sh` after changing `plugins/planner`.
