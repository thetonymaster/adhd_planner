# src

## Overview

The `src/` layout root for the `planner-setup` distribution. It holds one importable package, `planner_setup`. The wheel target in `../pyproject.toml` packages `src/planner_setup`; the custom build hook `../hatch_build.py` adds the repo's `examples/` and `docs/setup.md` to the wheel as `planner_setup/examples` (and `planner_setup/examples/setup.md`). An sdist places copies of both under `src/planner_setup/examples`, so a wheel built from the unpacked sdist finds them there instead; with neither source present the build fails.

## Subdirectories & Boundaries

- planner_setup: [./planner_setup/EGM.md](./planner_setup/EGM.md). The installer package:
  - CLI and menu (`cli.main`);
  - actions that install plugins through the `claude` CLI, merge vault paths and permissions into `~/.claude/settings.json`, edit `vaults.json` (add a vault, set the timezone), seed a starter vault, bring existing vaults up to date with the task board and the Task template's `priority` / `due` keys (`update-vaults`), and copy the example `CLAUDE.md`;
  - the Obsidian task-board support (`board_plugin.py`): merging the Board and Done (7 days) views into a vault's `Tasks.base`, and downloading the pinned, SHA-256-checked Kanban Bases View community plugin into `<vault>/.obsidian/plugins/` and enabling it;
  - pure settings merge;
  - path resolution;
  - atomic, backed-up JSON writes.
