# Setup

This repo is one plugin marketplace, `adhd-planner`, with three plugins:

| Plugin | What | Runs in |
|---|---|---|
| `planner` | 12 planning skills: triage, breakdown, time-blocking, A5 pages, habits | Claude Code, Cowork |
| `tasks` | Obsidian task notes: `task-start`/`task-park`/`task-switch`/`task-note`, session-start context, vault access | Claude Code, Cowork |
| `task-track` | Task band, pane, shared Pomodoro, `/note` `/done` `/openloop` (a mod) | Claude Code only |

## Claude Code — with the menu

```bash
uvx --from "git+ssh://git@github.com/thetonymaster/adhd_planner#subdirectory=setup" planner-setup
# or, from a checkout:
uvx --from ./setup planner-setup
```

- **Status**: marketplace and plugins installed? vault path, and is it in `additionalDirectories`?
- **Install plugins**: `claude plugin marketplace add` + `claude plugin install` for the ones you tick.
- **Settings**: writes `vaultPath` for `tasks` and `task-track`; optionally adds the vault to
  `additionalDirectories` and allows `Bash(obsidian:*)`.
- **Vault starter**: creates a starter vault, only if the path doesn't exist.
- **Example CLAUDE.md**: copies `examples/CLAUDE.md` only if you have no `~/.claude/CLAUDE.md`.
- **Cowork steps**: prints the section below.

Every item is also a subcommand: `planner-setup status`, `install [--plugins …]`,
`settings [--vault PATH] [--permissions]`, `vault [--vault PATH]`, `claude-md`, `cowork`.
Add `--dry-run` to see what would change, `--yes` to skip the confirmation.
Anything it changes is backed up under `~/.claude/backups/<timestamp>/` first.

## Claude Code — by hand

```bash
claude plugin marketplace add thetonymaster/adhd_planner
claude plugin install planner@adhd-planner
claude plugin install tasks@adhd-planner
claude plugin install task-track@adhd-planner
```

Set the vault path in `/config`, or in `~/.claude/settings.json`:

```json
{
  "pluginConfigs": {
    "tasks@adhd-planner": { "options": { "vaultPath": "/Users/you/vault" } },
    "task-track@adhd-planner": { "options": { "vaultPath": "/Users/you/vault" } }
  }
}
```

Empty means `$VAULT`, else `~/vault`.

## Settings plugins can't carry

Plugins cannot set permissions, so these stay in your own settings
(see [`examples/settings.example.json`](../examples/settings.example.json)):

- **Vault access.** The `tasks` plugin's PermissionRequest hook approves Read/Edit/Write/Glob/Grep
  inside the vault and adds the vault as a working directory for that session. To make it
  permanent and skip even the first prompt, add the vault to `permissions.additionalDirectories`.
- **Obsidian CLI.** `permissions.allow: ["Bash(obsidian:*)"]` lets skills run `obsidian` checks
  without asking. The hook never approves Bash.
- **CLAUDE.md.** [`examples/CLAUDE.md`](../examples/CLAUDE.md) is one person's file; copy what you want.

## Cowork

1. Claude Desktop → Cowork → Customize → Plugins → Add marketplace → `thetonymaster/adhd_planner`.
2. Install `planner` and `tasks` (`task-track` is Claude Code only).
3. Connect your vault folder (and your planner folder) to the session.
4. Try: "add a note to <task>: test".

In Cowork, `tasks` gives you `task-note` (show a task, add a Log line, check a Next item,
add an Open loop) and the start/park/switch skills. Its hooks print only the time when no
vault is found, so they never break a session.

**Cowork fallback.** If Cowork can't add the marketplace (the repo is private), build the
planner as a file and upload it: `bash scripts/build-plugin.sh`, then Customize → Plugins →
Upload → `planner.plugin`.

## Several vaults

One vault needs nothing here. For more, list them in `~/.config/adhd-planner/vaults.json` (or run `planner-setup add-vault`):

```json
{
  "default": "personal",
  "vaults": {
    "personal": { "path": "~/vault" },
    "work":     { "path": "~/work-vault", "folders": ["~/acme"] }
  }
}
```

Each session gets one vault: the one `/tasks:task-switch` last chose for it, else the vault holding a task whose `repo:` contains the folder, else the vault whose `folders` holds it, else `default`. Each vault keeps its own active task and timer. `/tasks:task-switch work:<slug>` moves a session to another vault. A broken file is named at session start and ignored (the single-vault settings apply).

## What each plugin needs

- **planner**: Python 3.10+ in the planner folder; `reportlab` for the printing skills;
  a Google Calendar connector for anything that touches your schedule.
- **tasks**: `python3` for the hooks; without it the session-start hook falls back to
  `Tasks/.active`, and the vault hook can't start, so you get the normal permission prompt.
- **task-track**: Claude Code only.
