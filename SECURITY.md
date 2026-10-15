# Security

## What runs without asking

The `tasks` plugin has a PermissionRequest hook (`plugins/tasks/hooks/vault-allow.py`)
that approves some file tools inside your Obsidian vault, so Claude doesn't prompt for
every note. In short: reads outside dot-folders, and writes only to `*.md` / `*.canvas`
notes (never `CLAUDE.md`) and three state files under `Tasks/`. It never approves Bash
or anything outside the vault, and trusts no vault that is `/`, your home folder or
above it, or inside `~/.claude`. The exact rules, and their limits:
[docs/setup.md → Settings plugins can't carry](docs/setup.md#settings-plugins-cant-carry).

`tasks`' SessionStart hook prints the active task note and, in each vault with a `Tasks/`
folder, deletes files in `Tasks/.session/` (per-session task overrides) that are older
than 14 days, with no prompt. Its shell fallback (no `python3`) deletes nothing.
`task-track` (a Claude Code mod) writes inside the vault on its own, without a permission
prompt:
- its timer state in `Tasks/.pomo.json`, through a temporary
  `Tasks/.pomo.json.<session>.tmp` that is renamed over it;
- the active task note, when you use `/note`, `/done`, `/openloop` or the task band and
  pane (Next buttons, Done, the note box);
- when focus time is logged, a line in that note's `## Log` and in the day's note
  `Daily/<date>.md`, which is created from `Templates/Daily.md`, or as a minimal stub if
  that template is absent.

`task-track`'s `breakSummaryAI` option (off by default) records prompt snippets, edited
files and commands in `Tasks/.pomo.json` and sends them to Claude Haiku for a one-line
summary.

## Turning it off

`claude plugin disable tasks@adhd-planner` turns off its hooks with it (you get the
normal permission prompts back); `claude plugin uninstall tasks@adhd-planner` removes it.

## Reporting a vulnerability

Use GitHub's private reporting: **Security → Report a vulnerability** on
[thetonymaster/adhd_planner](https://github.com/thetonymaster/adhd_planner/security).
If that button isn't there, open an issue that says only "security report, please send a
private contact", with no details, and the maintainer will reply with a private channel.
Please don't put the details of a security problem in a public issue. Fixes land on
`main`; there are no maintained older versions.
