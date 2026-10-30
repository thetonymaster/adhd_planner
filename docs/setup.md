# Setup

This repo is one plugin marketplace, `adhd-planner`, with three plugins:

| Plugin | What | Runs in |
|---|---|---|
| `planner` | 12 planning skills: triage, breakdown, time-blocking, A5 pages, habits | Claude Code, Cowork |
| `tasks` | Obsidian task notes: `create-task`/`task-start`/`task-park`/`task-switch`/`task-finish`/`task-note`/`task-list`, session-start context, vault access | Claude Code, Cowork |
| `task-track` | Task band, task and project-tasks panes, `/board` (Doing · Parked · Done), shared Pomodoro, `/note` `/done` `/openloop` (a mod) | Claude Code only |

> A productivity tool, not medical advice; not affiliated with any planner brand.

## Claude Code — with the menu

```bash
uvx --from "git+https://github.com/thetonymaster/adhd_planner#subdirectory=setup" planner-setup
# or, from a checkout:
uvx --from ./setup planner-setup
```

- **Status**: marketplace and plugins installed? vault path, and is it in `additionalDirectories`?
- **Install plugins**: `claude plugin marketplace add` + `claude plugin install` for the ones you tick.
- **Settings**: writes `vaultPath` for `tasks` and `task-track`; optionally allows `Bash(obsidian:*)`.
- **Vault starter**: creates a starter vault, only if the path doesn't exist, then offers the board plugin (see Task board in Obsidian).
- **Update existing vaults (task board)**: adds the board to vaults made before it (see Task board in Obsidian).
- **Add another vault**: registers a second vault in `~/.config/adhd-planner/vaults.json` (see Several vaults).
- **Timezone**: sets the zone times are stamped in (see Timezone).
- **Example CLAUDE.md**: copies `examples/CLAUDE.md` only if you have no `~/.claude/CLAUDE.md`.
- **Cowork steps**: prints the section below.

Every item is also a `planner-setup` subcommand: `status`, `install [--plugins …]`,
`settings [--vault PATH] [--permissions]`, `vault [--vault PATH]`, `update-vaults`,
`add-vault NAME --path PATH [--folder DIR]…`, `timezone ZONE [--existing-name NAME]`, `claude-md`, `cowork`.
`--dry-run` (show what would change) and `--yes` (skip the confirmation) go **before**
the subcommand: `planner-setup --dry-run install`, `planner-setup --yes settings --vault ~/vault`.
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

- **Vault access.** The `tasks` plugin's PermissionRequest hook approves, per call and without a
  prompt: Read/Glob anywhere in the vault except dot-folders (`.obsidian/`, `.git/`, ...), and Grep
  only for a single note file or with an anchored glob like `Projects/*.md` (literal folders;
  vault-wide `*.md` searches get the prompt because Claude Code searches hidden folders too; so does
  a `Projects/*.md` search while `Projects/` holds a hidden `.something.md`). Write/Edit of `*.md` /
  `*.canvas` notes outside dot-folders (never `CLAUDE.md` / `CLAUDE.local.md`, in any letter case)
  plus `Tasks/.active`, `Tasks/.pomo.json` and `Tasks/.session/*`; a write containing a dataviewjs
  fence, Templater (`<%`) or inline `$=` code gets the normal prompt, also when the fence sits
  inside a quote or list (`> `, `- `, `1. `). That check is a best-effort tripwire, not a guarantee:
  it cannot see code split across several writes, and other Obsidian plugins that execute note
  content are not detected, so review the plugins in vaults you let Claude write. Everything else
  gets the normal prompt. It trusts no vault that is `/`, your home folder or above it, or inside
  `~/.claude` or `$CLAUDE_CONFIG_DIR` (as written and `~`-expanded), and approves nothing while
  `vaults.json` has an error. Don't add the vault to `permissions.additionalDirectories` (if you
  did, remove it: in `acceptEdits` mode edits there skip the hook). A session started inside the
  vault in `acceptEdits` mode is auto-approved by Claude Code itself, outside the hook's reach. To
  turn the hook off, disable the `tasks` plugin's hooks or uninstall it.
- **Obsidian CLI.** `permissions.allow: ["Bash(obsidian:*)"]` lets skills run `obsidian` checks
  without asking. The hook never approves Bash.
- **CLAUDE.md.** [`examples/CLAUDE.md`](../examples/CLAUDE.md) is a short example; copy what you want.

## Cowork

1. Claude Desktop → Cowork → Customize → Plugins → Add marketplace → `thetonymaster/adhd_planner`.
2. Install `planner` and `tasks` (`task-track` is Claude Code only).
3. Connect your vault folder (and your planner folder) to the session.
4. Try: "add a note to <task>: test".

In Cowork, `tasks` gives you `task-note` (show a task, add a Log line, check a Next item,
add an Open loop), `task-list` (one project's tasks), `create-task` (backlog tasks, one or a batch), `task-finish` (close a task) and the start/park/switch skills. Its hooks print only the time when no
vault is found, so they never break a session.

**Cowork fallback.** If Cowork can't add the marketplace, build the
planner as a file and upload it: `bash scripts/build-plugin.sh`, then Customize → Plugins →
Upload → `planner.plugin`.

## Several vaults

One vault needs nothing here. For more, list them in `~/.config/adhd-planner/vaults.json` (or run `planner-setup add-vault`):

```json
{
  "default": "personal",
  "vaults": {
    "personal": { "path": "~/vault" },
    "work":     { "path": "~/work-vault", "folders": ["~/work"] }
  }
}
```

Each session gets one vault: the one `/tasks:task-switch` last chose for it, else the vault holding a task whose `repo:` contains the folder, else the vault whose `folders` holds it, else `default`. Each vault keeps its own active task and timer. `/tasks:task-switch work:<slug>` moves a session to another vault. A broken file is named at session start and ignored (the single-vault settings apply). The day-planning skills (`morning-startup`, `plan-day`, `plan-week`, `eod-shutdown`, `capture-triage`, `break-down-task`) look across every registered vault: they pull each vault's active task and inbox, label items `<vault>:<slug>`, and write each item back to its own vault's task and daily notes.

## Timezone

Times in your notes (the `Now:` line, focus and Log lines, which daily note today is) follow the machine's clock. If that clock is wrong for you, for example a WSL machine left on UTC, set your zone once per machine (`planner-setup` isn't installed; `uvx` runs it, as in the menu above):

```bash
uvx --from "git+https://github.com/thetonymaster/adhd_planner#subdirectory=setup" planner-setup timezone America/Mexico_City
```

With no `vaults.json` yet, this creates one holding this machine's vault as `personal`; pass `--existing-name NAME` (e.g. `--existing-name work`) to name it. Or add `"timezone"` to `vaults.json` by hand:

```json
{ "timezone": "America/Mexico_City", "default": "personal", "vaults": { "personal": { "path": "~/vault" } } }
```

Order: `vaults.json`'s `timezone`, else `$TZ`, else the system clock. A name that isn't an IANA zone is reported at session start (`Vault config warning:`) and ignored; your vaults keep working. Lines already written are not changed.

## Task board in Obsidian

`Tasks.base` has a **Board** view (columns Parked · Active · Done, by each note's `status`; drag a card to change it) and a **Done (7 days)** table. Dragging a card to Done sets `status: done` but not `finished:`, and both views show a done note only while `finished` is in the last 7 days, so the card disappears: finish a task with `/tasks:task-finish` (sets both), or fill in `finished: YYYY-MM-DD` yourself after the drag. The Board needs the community plugin [Kanban Bases View](https://github.com/xiwcx/obsidian-bases-kanban) (`kanban-bases-view`, pinned to 0.10.6) and Obsidian 1.10+ (Bases). A new starter vault gets both; for vaults you already have, run:

```bash
uvx --from "git+https://github.com/thetonymaster/adhd_planner#subdirectory=setup" planner-setup update-vaults
```

For every vault in `vaults.json` (or your one configured vault) it:

- **Tasks.base**: appends the Board and Done (7 days) views to `views:`, keeping your other views, sorts and properties (and CRLF line endings). Nothing to do when both are already there. If a view with one of those names exists with other content, or `views:` isn't a plain 2-space list, it asks **"Replace Tasks.base in <vault>? (backup kept)"**; yes swaps in the starter's file, no leaves yours alone. A vault without `Tasks.base` is skipped.
- **Plugin**: shows the source and asks **"Download xiwcx/obsidian-bases-kanban@0.10.6 into <vault>?"**, then downloads `manifest.json`, `main.js` and `styles.css` from that GitHub release into `<vault>/.obsidian/plugins/kanban-bases-view/` and adds `kanban-bases-view` to `.obsidian/community-plugins.json`, keeping the plugins already listed there. All three files are fetched before anything in the vault changes: offline or a failed download leaves the vault as it was (rerun later). Already at 0.10.6: no question, no download.

Then **reload Obsidian** (or close and reopen the vault), and allow community plugins in Settings → Community plugins if restricted mode is on. `--dry-run` shows all of this and writes nothing; `--yes` answers both questions with yes. Changed files are backed up under `~/.claude/backups/<timestamp>/<vault name>/` first.

## What each plugin needs

- **planner**: Python 3.10+ in the planner folder; `reportlab` for the printing skills;
  a Google Calendar connector for anything that touches your schedule.
- **tasks**: `python3` for the hooks; without it the session-start hook falls back to
  `Tasks/.active`, and the vault hook can't start, so you get the normal permission prompt.
- **task-track**: Claude Code only.
