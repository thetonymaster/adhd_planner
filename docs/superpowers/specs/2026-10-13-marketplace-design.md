# One marketplace for Claude Code and Cowork — design

Date: 2026-10-13 · Branch: `feat/marketplace`

## Goal

This repo becomes one plugin marketplace (`adhd-planner`) with three plugins. Hooks ship
inside plugins instead of being merged into `~/.claude/settings.json`. Claude Code installs
all three; Cowork installs the two it can run. A `uvx` setup menu replaces `install.sh` and
`merge-settings.py` for the parts plugins cannot carry.

## Decisions (from Q)

- Three plugins: `planner`, `tasks`, `task-track`.
- Q's own `~/.claude/CLAUDE.md` stays as is; the repo copy becomes an example.
- Q's engineering skills (`autonomy-check`, `composition`, `handoff`, `investigation`) and
  `rules/composition.md` leave this repo. Q's installed copies in `~/.claude/` are untouched.
- Cowork gets the planner skills, plus task notes limited to reading a task, adding notes,
  and checking items on notes that already exist in Obsidian. No session-start injection there.
- Setup helper: a Python CLI run with `uvx`, menu built with `questionary`.
- No migration feature: Q's old local install is removed once, by hand, at the end of
  implementation (see Rollout).

## Facts this design relies on

Verified from Anthropic docs on 2026-10-13:
- One `marketplace.json` can list several plugins with relative sources (`"./plugins/x"`).
  Required: `name`, `owner`, `plugins[].name`, `plugins[].source`.
- Plugin hooks get `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}`, and userConfig values as
  `CLAUDE_PLUGIN_OPTION_<KEY>`.
- A plugin's `settings.json` cannot set permissions (only `agent` and `subagentStatusLine`
  are kept).
- A `PermissionRequest` hook can approve a request and return
  `updatedPermissions: [{type: "addDirectories", ...}]`.
- Mods (`modules` in `hooks.json`) do not run in Cowork.
- Cowork installs plugins from Customize → Plugins → Add marketplace (GitHub `owner/repo`),
  and supports skills, agents, hooks and connectors.

Not known:
- Which interpreters Cowork hooks have, and where they run.
- Whether Cowork can add a **private** GitHub repo as a marketplace. This repo is private.

## Layout

```
.claude-plugin/marketplace.json   name "adhd-planner", owner Antonio Cabrera, 3 plugin entries
plugins/
  planner/      git mv planner-plugin/            12 skills + tools/ seed; no hooks
  tasks/        new plugin
    .claude-plugin/plugin.json   userConfig: vaultPath (empty → $VAULT → ~/vault)
    skills/     task-start, task-park, task-switch, obsidian-vault (git mv from claude-config/skills)
                task-note (new)
    hooks/hooks.json
      SessionStart (startup|resume|clear|compact) → ${CLAUDE_PLUGIN_ROOT}/hooks/load-task.sh
      UserPromptSubmit                            → date '+Now: %H:%M'
      PermissionRequest                           → ${CLAUDE_PLUGIN_ROOT}/hooks/vault-allow.py
    hooks/load-task.sh   git mv from claude-config/hooks/
    hooks/vault-allow.py new
  task-track/   git mv claude-config/task-track/  mod; marketplace description says "Claude Code only"
setup/          uv project, console script `planner-setup`
examples/
  CLAUDE.md               git mv claude-config/CLAUDE.md, header line: "Example — copy and adapt"
  settings.example.json   annotated: additionalDirectories, Bash(obsidian:*)
  vault-starter/          git mv claude-config/vault-starter/
docs/setup.md             manual install steps for Code and Cowork, settings notes
```

Removed: `claude-config/skills/{autonomy-check,composition,handoff,investigation}`,
`claude-config/rules/`, `claude-config/install.sh`, `claude-config/merge-settings.py`,
`claude-config/settings.snippet.json`. `claude-config/` disappears.

Kept for now: `scripts/build-plugin.sh` and `planner.plugin`. They are the Cowork fallback
if adding a private GitHub marketplace fails (Rollout step 4). They are deleted after that
step passes, or rewritten to build `planner` and `tasks` zips from `plugins/` if it fails.

Not touched: the root `tools/`, the HTML pages, `inbox.md`, `habits*.json` (Q's planner folder).

## Plugins

### planner
Content unchanged; only the path moves. `plugin.json` version bumps to 0.3.0.

### tasks
**load-task.sh.** Same selection logic as today. Two changes:
1. The vault comes from `CLAUDE_PLUGIN_OPTION_VAULTPATH`, then `$VAULT`, then `~/vault`.
2. It always exits 0. With no vault or no `python3`, it prints only the `Now:` line, so it
   never breaks a session (Cowork included).

**vault-allow.py.** A PermissionRequest hook with this logic:
1. Read the request JSON from stdin.
2. Resolve every path in the tool input: `file_path`, `path`, `notebook_path`, and the
   directory argument of `Read`/`Edit`/`Write`/`Glob`/`Grep`.
3. If **every** path is inside the resolved vault, return allow plus
   `addDirectories` (vault, session scope).
4. Otherwise print nothing and exit 0, so the normal prompt appears.

Bash requests are never auto-approved. Python stdlib only.

**task-note skill.**
- Finds the vault: a connected folder named `vault` or holding `Tasks/` and `Daily/`, else
  `$VAULT`, else `~/vault`.
- Actions: show a task (Goal / Next / Open loops), list open tasks (`status` not `done`), add
  a Log line `- [[YYYY-MM-DD]] HH:MM — text`, check or uncheck a Next item, add an Open loop.
- Never creates, renames or moves notes. Never deletes lines; it strikes through and says why.
- Defers to `obsidian-vault` for link and format rules.
- In Code, task-track's `/note`, `/done` and `/openloop` remain the no-model-turn path;
  task-note is the model-driven equivalent.

**Skill names gain the plugin prefix** (`/tasks:task-park`). Q's `~/.claude/CLAUDE.md` is not
edited; Q updates its references.

### task-track
Content unchanged; only the path moves. Its `vaultPath` userConfig stays.

## Setup CLI (`setup/`)

Run:
- From GitHub (private, SSH):
  `uvx --from "git+ssh://git@github.com/thetonymaster/adhd_planner#subdirectory=setup" planner-setup`
- From a checkout: `uvx --from ./setup planner-setup`

The bare command opens the menu. Each item is also a subcommand for tests and scripts:
`status`, `install`, `settings`, `vault`, `claude-md`, `cowork`. Global flags: `--dry-run`,
and `--yes` to skip confirmation.

| Item | Does |
|---|---|
| Status (default, read-only) | Marketplace added? Each plugin installed/enabled? Vault path and whether it exists. Vault in `additionalDirectories`? |
| Install plugins (Code) | Checklist of the 3 plugins (all ticked). Runs `claude plugin marketplace add <source>` (the checkout path when run from one, else `thetonymaster/adhd_planner`), then `claude plugin install <p>@adhd-planner`. |
| Settings | Writes the vault path to `pluginConfigs["tasks@adhd-planner"].options.vaultPath` and `pluginConfigs["task-track@adhd-planner"].options.vaultPath` (key format verified in the settings reference). Optional: adds the vault to `permissions.additionalDirectories` and `Bash(obsidian:*)` to `permissions.allow`. |
| Vault starter | Copies `examples/vault-starter` to the vault path only if it does not exist, renaming `_claude` to `.claude`. |
| Example CLAUDE.md | Copies it only if `~/.claude/CLAUDE.md` is missing; otherwise prints the example path. |
| Cowork | Prints the Cowork steps from `docs/setup.md`. |

`examples/` is packaged as data inside the wheel, so `uvx` from GitHub works without a checkout.

**Every write:**
1. List the planned changes (key names, never values).
2. Ask for confirmation, unless `--yes`.
3. Copy the target to `~/.claude/backups/<timestamp>/`.
4. Write a temp file, re-parse it, rename it over.

**Failures:**
- Invalid `settings.json`: stop with the path and the parse error; nothing is written.
- `claude` missing from `PATH`: say so and skip Install.
- `claude` exits non-zero: show its stderr verbatim and stop that item.
- No silent defaults: an unset vault path is asked for, never guessed past `$VAULT` → `~/vault`.

**Modules** (`setup/src/planner_setup/`):

| File | Holds |
|---|---|
| `settings.py` | Pure functions over dicts: merge `pluginConfigs` and permissions, diff for display. Ported from `merge-settings.py`. |
| `files.py` | Backup and atomic write. |
| `claude_cli.py` | `subprocess` wrapper around `claude plugin …`; returns stdout, stderr and the exit code. |
| `paths.py` | Vault resolution and packaged example paths. |
| `cli.py` | argparse subcommands and the questionary menu, which calls the same functions. |

## Testing

All of these must pass:
1. `claude plugin validate` on the repo root (marketplace) and on `plugins/planner`,
   `plugins/tasks` and `plugins/task-track`.
2. `cd plugins/task-track && claude plugin test .` — the existing suite, unchanged.
3. `python3 -m unittest discover -s tests`:
   - `test_load_task.py` points at the new path and adds cases for the userConfig vault and
     the missing-vault exit 0.
   - New `test_vault_allow.py` covers: inside the vault → allow + addDirectories; any path
     outside → no output; symlink or `..` escaping the vault → no output; Bash → no output.
4. `cd setup && uv run pytest`, with a temp `HOME` and a fake `claude` script on `PATH` that
   records its arguments. It covers merge idempotence, invalid JSON aborting, backup created,
   `--dry-run` writing nothing, and the `claude` failure surfaced.
5. `uvx --from ./setup planner-setup status` against the temp `HOME` prints a full status.

## Rollout (on Q's machine)

1. Repo checks above pass.
2. List Q's old local install and delete it after Q confirms the list. Everything removed
   is copied to `~/.claude/backups/<timestamp>/` first. The list:
   - in `~/.claude/settings.json`: the `load-task.sh` and `date` hooks, and the
     task-track entry in `CLAUDE_CODE_PLUGIN_DIRS`
   - `~/.claude/hooks/load-task.sh`
   - `~/.claude/skills/{task-start,task-park,task-switch,obsidian-vault}`
3. Install from `uvx` (Install + Settings). Start a new `claude` session in this repo and check:
   - SessionStart shows this repo's task Next exactly once
   - `/tasks:task-park` resolves
   - the task-track band shows
   - `Now:` appears on each prompt
4. Cowork (Q, ~10 min): add the marketplace, install `planner` + `tasks`, start a session with
   the vault folder connected, ask "add a note to set-up-vault: test", and check the Log line
   lands and no hook error appears. Then resolve `build-plugin.sh` as described under Layout.

## Out of scope

- Porting task-track to Cowork.
- Migration tooling for other users' old installs.
- Editing Q's `~/.claude/CLAUDE.md`.
