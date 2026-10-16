# AGENTS.md

Guidance for coding agents working in this repository. `CLAUDE.md` imports this file, so Claude Code reads the same rules.

## Checks

Four suites; run the ones covering what you touched.

| Covers | Command |
|---|---|
| `plugins/tasks/hooks/*` (bash + Python hooks) | `python3 -m unittest discover -s tests` |
| `setup/` (`planner-setup` CLI) | `cd setup && uv run pytest` |
| `plugins/task-track` (TypeScript mod) | `cd plugins/task-track && claude plugin test .` |
| `.claude/skills/planner-dev` (repo dev tools) | `cd .claude/skills/planner-dev && claude plugin test .` |
| any plugin's manifest/skills/hooks | `claude plugin validate plugins/<name>` |

Single test: `python3 -m unittest tests.test_vaults.<Class>.<method>`, `cd setup && uv run pytest tests/test_cli.py -k <name>`.

CI (`.github/workflows/ci.yml`) runs the Python suite, the `setup` pytest, `uv build` and `claude plugin validate` for the three plugins and the marketplace on every PR; the task-track and planner-dev `claude plugin test` suites run locally only.

`/planner-dev:release-plugin` runs the right subset before a PR. Build the Cowork upload file: `bash scripts/build-plugin.sh` → `planner.plugin` (validates, runs `tests/`, zips `plugins/planner`). `planner.plugin` is committed; never edit it by hand, rebuild it when `plugins/planner` changes.

## Layout

The repo is a **plugin marketplace** (`.claude-plugin/marketplace.json`, name `adhd-planner`) with three plugins under `plugins/`:
- `planner` — 12 skills plus a **seed copy** of the Python tools (`plugins/planner/tools/`). Works in Claude Code and Cowork.
- `tasks` — Obsidian task-note hooks (`SessionStart` → `load-task.sh` injects the active note's Goal/Next/Open loops; `PermissionRequest` → `vault-allow.py` auto-approves file tools inside the vault) and the task-start/park/switch/note skills. Claude Code and Cowork.
- `task-track` — a Claude Code–only mod (`hooks/register.tsx`): task band, `/task` pane, `/note` `/done` `/openloop` `/pomo` without a model turn, shared Pomodoro in `vault/Tasks/.pomo.json`. Tests import from `claude-code/testing`. For live development set `CLAUDE_CODE_PLUGIN_DIRS=plugins/task-track`.

Why the tools exist twice: an installed plugin is read-only, but the scripts write their data files. So the plugin ships know-how and a seed `tools/`; `/planner:setup` copies it into the user's planner folder, and skills run `python3 tools/…` there. A change to a tool usually belongs in `plugins/planner/tools/` (what users get).

`setup/` is the `planner-setup` installer (uv project, `questionary`): installs the plugins, writes `pluginConfigs` vault paths and permissions, seeds a vault from `examples/vault-starter/`. It packages `../examples` and `../docs/setup.md` into the wheel.

## Vault resolution (shared contract)

`plugins/tasks/hooks/vaults.py` + `session_task.py` (Python) and `plugins/task-track/hooks/resolve.ts` (TypeScript) implement the same rules and must stay in sync. The same order is also spelled out in prose at the top of the `tasks` skills (`task-start`, `task-park`, `task-switch`, `obsidian-vault`):
- Vault: `$ADHD_PLANNER_VAULTS`, else `~/.config/adhd-planner/vaults.json`, if valid (session's task-switch choice → vault with a non-`done` task whose `repo:` holds the cwd → vault whose `folders` holds it → `default`); otherwise the plugin's `vaultPath` option, else `$VAULT`, else `~/vault`.
- Task: `Tasks/.session/<session-id>` → non-`done` note whose `repo:` holds the cwd → `Tasks/.active`.

Shared fixtures for these cases live in `plugins/task-track/tests/fixtures/vault-cases.ts`; the Python tests are `tests/test_vaults.py` and `tests/test_load_task.py`.

## Conventions

- `.claude/skills/planner-dev/` is a repo-local plugin (auto-loaded in this repo, not in the marketplace): the release-plugin skill, the `skill-trigger-reviewer` agent (run it after editing any skill description), a guard denying edits to `planner.plugin` / `setup/uv.lock`, and `claude plugin validate plugins/<name>` after every edit under `plugins/<name>/` (failures reach the model with the edit's result). These only run inside Claude Code; any other agent applies the same rules by hand: don't edit `planner.plugin` or `setup/uv.lock`, and run `claude plugin validate plugins/<name>` after touching a plugin.

- Bump `version` in a plugin's `.claude-plugin/plugin.json` when it changes.
- Skill `description` fields carry the routing ("not X, use Y"); when editing one, check the sibling skills it names so triggers don't overlap.
- Features go spec → plan → implementation: `docs/superpowers/specs/` and `docs/superpowers/plans/`. `.superpowers/sdd/` is scratch from those runs.
- User-facing install/config docs live in `docs/setup.md`; keep it in step with `setup/` and the plugin options.
