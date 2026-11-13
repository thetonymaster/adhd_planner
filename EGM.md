# ADHD Planner Blueprint

## System Overview

A Claude plugin marketplace, `adhd-planner` (`.claude-plugin/marketplace.json`), for ADHD-friendly
planning in Claude Code and Cowork. It ships three plugins (`planner`, `tasks`, `task-track`), a
`planner-setup` installer that wires them into a user's machine, and a build script that packages
`plugins/planner` as the committed Cowork upload file `planner.plugin`. Human-facing docs stay in
[README.md](./README.md) and [AGENTS.md](./AGENTS.md); this file is the contract index.

## Subdirectories & System Boundaries

- plugins: [./plugins/EGM.md](./plugins/EGM.md) - The three marketplace plugins. They share the
  user's Obsidian vault but import no code from each other.
  - planner: [./plugins/planner/EGM.md](./plugins/planner/EGM.md) - 12 planning skills plus the
    seed Python `tools/` that `/planner:setup` copies into the user's planner folder.
  - tasks: [./plugins/tasks/EGM.md](./plugins/tasks/EGM.md) - Task-note hooks (SessionStart
    context, `Now:` stamp, SessionEnd park, vault auto-approve) and the task skills
    (`create-task`, `task-start`, `task-park`, `task-switch`, `task-finish`, `task-note`,
    `task-list`, `obsidian-vault`).
  - task-track: [./plugins/task-track/EGM.md](./plugins/task-track/EGM.md) - Claude Code-only mod:
    task band, `/task`, `/project-tasks` and `/board` panes, shared Pomodoro, `/note` `/done`
    `/openloop` `/pomo`.
- setup: [./setup/EGM.md](./setup/EGM.md) - The `planner-setup` uv project: installs the plugins,
  merges `pluginConfigs` and permissions into `~/.claude/settings.json`, manages `vaults.json`,
  seeds a vault from `examples/vault-starter`, and (`update-vaults`) adds the task board to existing
  vaults: Board views in `Tasks.base` plus the pinned Obsidian plugin `kanban-bases-view`.
- scripts: [./scripts/EGM.md](./scripts/EGM.md) - `build-plugin.sh`: validates, tests and zips
  `plugins/planner` into `planner.plugin`.

Not contracted (no source code): `docs/` (specs, plans, `setup.md`), `examples/` (vault starter,
packaged into the `setup` wheel), `tests/` (Python suite for the hooks and tools).

## Global Invariants

- Vault and task resolution is one contract with three implementations that must stay in sync:
  `plugins/tasks/hooks/vaults.py` + `session_task.py` (Python), `plugins/task-track/hooks/resolve.ts`
  (TypeScript), and prose in the `tasks` skills (`task-start`, `task-park`, `task-switch`,
  `create-task`, `task-finish`, `obsidian-vault` state the hook's order word for word; `task-note`
  and `task-list` have their own "Find the vault" list) and several `planner` skills (e.g.
  `eod-shutdown`, `break-down-task`). Shared fixtures: `plugins/task-track/tests/fixtures/vault-cases.ts`.
  Known gaps today: `vaults.py` resolves symlinks and `resolve.ts` does not (accepted: the mod API
  has no realpath, multi-vault spec §4); `task-list` and `task-note` skip the `vaultPath` option and
  add a connected folder named `vault` before `$VAULT` (the Cowork-first order of the marketplace
  spec's task-note section; the session-start `Vault:` line comes first, so Claude Code sessions
  land on the same vault).
- `setup/src/planner_setup` and `docs/setup.md` must agree with that resolution order, the
  `vaults.json` location and the plugin options: `paths.py` holds `$VAULT` → `~/vault` and the
  `vaults.json` location, `actions._current_vault` adds the `vaultPath` option in front.
- Task slugs match `^[a-z0-9][a-z0-9-]*$` on every production path (Python, TypeScript, bash).
- Task `status` lifecycle, shared by the skills, `park_on_end.py`, the mod's `/board` and
  `/project-tasks` and the starter `Tasks.base`: `create-task` and the starter template write
  `parked`; `task-start`/`task-switch` set `active`; `task-park` and the SessionEnd hook (not on
  `/clear`) set `parked`; `task-finish` sets `done` plus `finished:`. Resolution and repo binding
  skip `done` notes. "Done" on a board means `done` with `finished` in the last 7 days, today
  included (`board.ts` `buildBoard`, `board_plugin.DONE_WINDOW`).
- The marketplace name `adhd-planner` and the plugin IDs `planner`, `tasks`, `task-track` are
  hard-coded in `setup/src/planner_setup/settings.py` (and the name in `paths.py`) and must match
  `marketplace.json`.
- Tool changes belong in `plugins/planner/tools/` (the seed users get), not in a user's copy.
- Never edit `planner.plugin` or `setup/uv.lock` by hand; rebuild with `bash scripts/build-plugin.sh`
  whenever `plugins/planner` changes, and let `uv` regenerate the lock. The build zips every file
  under `plugins/planner` except `.DS_Store`, `EGM.md`, `__pycache__/` and `*.pyc`, so these
  contracts never ship to users.
- Bump `version` in a plugin's `.claude-plugin/plugin.json` when it changes, and run
  `claude plugin validate plugins/<name>` after each edit.

## Global Side Effects

- The user's Obsidian vault: task notes (including the SessionEnd hook's `status: parked` and
  `parked: session ended` Log line), `Tasks/.active`, `Tasks/.session/<id>`, `Tasks/.pomo.json` (+ `.pomo.flock`),
  daily-note Log lines.
- The user's planner folder: copied tools, `inbox.md`, habit logs, `tools/out/` plans and PDFs.
- `planner-setup` writes `~/.claude/settings.json` and `~/.config/adhd-planner/vaults.json`
  (each backed up under `~/.claude/backups/` first), runs `claude plugin marketplace add` /
  `claude plugin install` (no backup), copies `~/.claude/CLAUDE.md` only when it is absent (no
  backup), and can create a vault by copying `examples/vault-starter`. For the task board it edits
  a vault's `Tasks.base`, `.obsidian/community-plugins.json` and `.obsidian/plugins/kanban-bases-view/`
  (backed up under `~/.claude/backups/<timestamp>/<vault name>/` by `update-vaults`), after
  downloading the plugin's 0.10.6 release assets from GitHub and checking each pinned SHA-256.
- Permission outcomes for vault file tools (`tasks` PermissionRequest hook, allow-only).
- Google Calendar through MCP (planner skills only); `claude-haiku-5-5` calls when task-track's
  `breakSummaryAI` is on.
- `planner.plugin` in the repo, rewritten by every successful build.

## System Verification

- Run: `python3 -m unittest discover -s tests` (tasks hooks, planner tools)
- Run: `cd setup && uv run pytest` (installer; CI runs `uv run --locked pytest` and `uv build`)
- Run: `cd plugins/task-track && claude plugin test .` (task-track mod, local only)
- Run: `cd .claude/skills/planner-dev && claude plugin test .` (repo dev tools, local only)
- Run: `claude plugin validate plugins/<name>` (any plugin) and `claude plugin validate .`
  (marketplace, in CI)
