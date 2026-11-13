# setup

## Overview

The `planner-setup` installer. It is a uv project with one runtime dependency, `questionary>=2.0`, and a hatchling build. It is the scripted way to install the `adhd-planner` marketplace and configure a machine for it:

- installs the `planner`, `tasks` and `task-track` plugins through the `claude` CLI;
- writes the `pluginConfigs` vault paths and optional permissions into `~/.claude/settings.json`;
- manages `~/.config/adhd-planner/vaults.json`;
- seeds a vault from the repo's `examples/vault-starter/`;
- adds the task board to vaults: merges the Board and Done (7 days) views into each vault's `Tasks.base` and installs the pinned community Obsidian plugin `kanban-bases-view` (xiwcx/obsidian-bases-kanban 0.10.6) from its GitHub release (`src/planner_setup/board_plugin.py`, `update-vaults` and the vault starter);
- adds `priority: p3` and `due:` to an existing vault's `Templates/Task.md` when missing (`update-vaults`, no prompt);
- replaces the original one-line `## Tasks` section of `Templates/Project.md` and of each note directly in `Projects/` and `Areas/` with the starter Project template's Base block (`update-vaults`, one prompt per vault; edited sections are listed and left alone).

The user-facing documentation for all of this is [`docs/setup.md`](../docs/setup.md). Keep it in step with this directory.

## Interface

- **Console script** `planner-setup` → `planner_setup.cli:main` (`pyproject.toml` `[project.scripts]`). Subcommands and actions: [./src/planner_setup/EGM.md](./src/planner_setup/EGM.md).
- **Source layout:** [./src/EGM.md](./src/EGM.md).
- **`hatch_build.py` → `CustomBuildHook(BuildHookInterface)`**, whose `initialize(version, build_data)` bundles the example files into the wheel. Where it looks for them:
  1. **From a checkout:** it force-includes `../examples` as `planner_setup/examples` and `../docs/setup.md` as `planner_setup/examples/setup.md`.
  2. **From an unpacked sdist:** it uses the copies already under `src/planner_setup/examples`. `[tool.hatch.build.targets.sdist.force-include]` in `pyproject.toml` puts them there.
  3. **Neither found:** it raises `FileNotFoundError` naming both locations.
- **`pyproject.toml`:**
  - name `planner-setup`, version `0.1.0`;
  - `requires-python >=3.10`;
  - dev group `pytest>=8`;
  - wheel packages `src/planner_setup`.
- **What the wheel carries** (checked with `uv build`): the `planner_setup` modules, including `board_plugin.py`; `planner_setup/examples/` (`CLAUDE.md`, `settings.example.json`, `vault-starter/` with `Tasks.base`); `planner_setup/examples/setup.md`. `update-vaults` reads the bundled starter `Tasks.base` as the replacement file.

## Invariants

- **The example files live outside `setup/`.** `../examples` and `../docs/setup.md` are the only sources. The wheel and sdist carry copies; never commit copies inside `src/planner_setup/examples` (a convention: `setup/.gitignore` does not ignore that path). At runtime, `paths.examples()` prefers the bundled copy and falls back to `<repo>/examples`.
- **Do not edit `uv.lock` by hand.** It is generated, and the repo's planner-dev guard denies edits to it. Change dependencies in `pyproject.toml` and let `uv` regenerate the lock.
- **`docs/setup.md` must match the code:** the subcommands, the flags, `vaults.json` behaviour, the plugin option names, and the "Task board in Obsidian" section (`update-vaults` questions, the `kanban-bases-view` pin, backups under `~/.claude/backups/<timestamp>/<vault name>/`). The wheel also ships it as `examples/setup.md`. Tests pin parts of this: every long flag each `cli._parser()` subcommand defines appears in its `docs/setup.md` entry (`tests/test_cli.py`), and the Cowork steps 2-4 `actions.cowork` prints match the `## Cowork` list (`tests/test_actions.py`). The docs say that backups (of `settings.json`, `vaults.json`, a vault's `Tasks.base` and board plugin files) go under `~/.claude/backups/<timestamp>[-N]/` and that `claude plugin` installs are not backed up, and that `add-vault` / `timezone` add this machine's vault (`personal`, or `--existing-name`) as the default when `vaults.json` has no vaults yet (missing file, or no `"vaults"` entries). Known mismatch today:
  - `docs/setup.md:144` says a vault without `Tasks.base` is skipped, but `update_vaults` still offers it the board plugin (`actions.py:239-240`).
- **Repo-wide rules:**
  - The marketplace name `adhd-planner` and the plugin IDs are defined in `.claude-plugin/marketplace.json`. `src/planner_setup/settings.py` and `src/planner_setup/paths.py` hard-code them.
  - The vault rules must match `plugins/tasks/hooks/vaults.py` and `plugins/task-track/hooks/resolve.ts`.
  - The board's 7-day Done window (`board_plugin.DONE_WINDOW`, `finished >= today() - "6 days"`) matches `/board` in task-track (`buildBoard(..., days = 7)` in `plugins/task-track/hooks/board.ts`), and the Board's columns follow the task `status` lifecycle (`parked`, `active`, `done`).
  - The starter `examples/vault-starter/Tasks.base` holds `BOARD_VIEW` and `DONE_VIEW` verbatim, so `merge_base` leaves it unchanged (`tests/test_board_plugin.py`).
  - `PLUGIN_VERSION` and `PLUGIN_SHA256` change together: every release asset is checked against its pinned SHA-256 before anything in the vault changes.

## Side Effects

- **Build:** `uv build` reads `../examples` and `../docs/setup.md` and writes `dist/`, which `.gitignore` ignores along with `.venv/` and `.pytest_cache/`.
- **Runtime:** see [./src/planner_setup/EGM.md](./src/planner_setup/EGM.md#side-effects). It writes to `~/.claude/` and `vaults.json`, runs `claude plugin ...` in a subprocess, and can create a vault directory. `update-vaults` and the vault starter also download three files from `https://github.com/xiwcx/obsidian-bases-kanban/releases/download/0.10.6/` (after a confirmation, unless `--yes`), and write `<vault>/Tasks.base`, `<vault>/.obsidian/plugins/kanban-bases-view/` and `<vault>/.obsidian/community-plugins.json`, backing up what they replace.

## Verification

- Run: `cd setup && uv run --locked pytest` (124 tests pass on the current tree).
- Build: `cd setup && uv build` (CI runs both, `uv run --locked pytest` and `uv build --out-dir "$RUNNER_TEMP/dist"`: `.github/workflows/ci.yml`). It builds the sdist, then the wheel from the sdist.
