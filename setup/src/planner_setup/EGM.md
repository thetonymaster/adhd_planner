# planner_setup

## Overview

The `planner-setup` installer package. It installs the `adhd-planner` marketplace plugins through the `claude` CLI, merges vault paths and permissions into `~/.claude/settings.json`, edits the vault registry (`vaults.json`), seeds a starter vault, brings existing vaults up to date (board views in `Tasks.base`, `priority` and `due` in `Templates/Task.md`, the pinned Kanban Bases View Obsidian plugin), and copies an example `CLAUDE.md`. `cli.py` exposes the same actions two ways: a `questionary` menu (no arguments) and argparse subcommands.

Layering, top to bottom:

| Module | Role |
|---|---|
| `cli.py` | Entry point: argument parsing, the interactive menu, building `actions.Ctx` from the real environment |
| `actions.py` | The user-facing operations; each returns an exit code and reports through `ctx.say` |
| `settings.py` | Pure functions over settings dicts (what setup wants, merging it in) |
| `paths.py` | Path resolution: vault, `vaults.json`, bundled examples, repo checkout, marketplace source |
| `board_plugin.py` | The task board's Obsidian side: the pinned community plugin (download, hash check, install, enable) and merging the board views into a `Tasks.base` |
| `files.py` | JSON load, timestamped backups, atomic writes |
| `claude_cli.py` | Thin wrapper over the `claude` executable |

## Interface

### `cli.py`

- `main(argv: list[str] | None = None) -> int`: console script `planner-setup` (`pyproject.toml` → `planner_setup.cli:main`).
- Global flags: `--yes` (do not ask before writing), `--dry-run` (show what would change, write nothing).
- Subcommands: `status`; `install [--plugins ...]`; `settings [--vault P] [--permissions]`; `vault [--vault P]`; `update-vaults`; `add-vault NAME --path P [--folder F]... [--existing-name N]`; `timezone ZONE [--existing-name N]`; `claude-md`; `cowork`.
- No subcommand: interactive menu (`MENU`: Status, Install plugins, Settings, Vault starter, Update existing vaults (task board), Add another vault, Timezone, Example CLAUDE.md, Cowork steps, Quit), which needs a TTY on stdin. Without a TTY it exits 2.
- `_existing_name(ctx, questionary)`: the menu's `--existing-name`. Asks for a kebab-case name only when `vaults.json` has no `vaults` yet (the same test `add_vault` / `set_timezone` seed on); an empty answer skips the action.

### `actions.py`

- `Ctx` dataclass: `home`, `cwd`, `env`, `yes`, `dry_run`, `confirm(question) -> bool`, `say(text)`, `checkout: Path | None`; property `settings_path` (`home/.claude/settings.json`). Every action takes its environment from `Ctx`, so tests inject fakes.
- `status(ctx) -> int`: marketplace and plugin state from `claude plugin marketplace list --json` and `claude plugin list --json`, the current vault, and whether that vault is in `permissions.additionalDirectories`.
- `install(ctx, plugins) -> int`: adds the marketplace if missing, then runs `claude plugin install <p>@adhd-planner` for each plugin not yet installed.
- `configure(ctx, vault, permissions) -> int`: merges `settings.desired(...)` into `settings.json`.
- `seed_vault(ctx, vault, fetch=board_plugin.download) -> int`: copies `examples/vault-starter` to `vault`, renames `_claude/` to `.claude/`, then offers the board plugin (`_board_plugin`) and prints `RELOAD` when it is in place. A failed plugin install is reported but still returns 0.
- `update_vaults(ctx, fetch=board_plugin.download) -> int`: for every vault `_registered_vaults` returns (each `vaults.json` vault; without one, the single vault `_current_vault` names, as `vault`), skipping missing folders: `_merge_tasks_base`, then `_add_priority_keys` (adds the missing of `priority: p3` and `due:` to `Templates/Task.md`'s frontmatter; no template or no frontmatter: one message, nothing written), then `_board_plugin`, with backups under `<backup_dir>/<vault name>/`. Prints `RELOAD` unless dry run. Returns 1 when any plugin install failed, else 0.
- `_merge_tasks_base(ctx, vault, backups)`: `board_plugin.merge_base` on `<vault>/Tasks.base` (read as bytes, so CRLF survives). `added`: backs up and writes without asking; `unchanged`: says so; `conflict`: asks to replace the file with the starter's (backup kept). No `Tasks.base`: says so and adds nothing.
- `_board_plugin(ctx, vault, fetch, backups) -> bool | None`: True when the pinned plugin is in place now, False when `install_plugin` failed, None when skipped (declined or dry run). Asks only when the vault's copy is not `PLUGIN_VERSION`.
- `RELOAD`: the "reload Obsidian; allow community plugins" line.
- `add_vault(ctx, name, path, folders, existing_name="personal") -> int`: registers a vault in `vaults.json`.
- `set_timezone(ctx, zone, existing_name="personal") -> int`: sets `vaults.json`'s `timezone`.
- `claude_md(ctx) -> int`: copies `examples/CLAUDE.md` to `~/.claude/CLAUDE.md` when absent.
- `cowork(ctx) -> int`: prints the manual Cowork install steps. Writes nothing.

### `board_plugin.py`

- Pin: `PLUGIN_ID = "kanban-bases-view"`, `PLUGIN_VERSION = "0.10.6"`, `PLUGIN_REPO = "xiwcx/obsidian-bases-kanban"`, `PLUGIN_FILES = ("manifest.json", "main.js", "styles.css")`, `PLUGIN_SHA256` (one digest per file; change together with `PLUGIN_VERSION`).
- Views: `BOARD_VIEW` (`kanban-view` named `Board`, grouped by `note.status`, columns parked · active · done), `DONE_VIEW` (table named `DONE_VIEW_NAME = "Done (7 days)"`), both filtered by `DONE_WINDOW` (`finished >= today() - "6 days"`, the 7 days `/board` in task-track shows). They must match the views in `examples/vault-starter/Tasks.base`.
- `merge_base(text) -> (text, "added" | "unchanged" | "conflict")`: appends the missing views at the end of `views:`, line by line, keeping every other line and the file's line endings. `conflict` (text untouched) when a view with one of their names differs, or `views:` is missing or not a 2-space block list.
- `plugin_dir(vault)` (`<vault>/.obsidian/plugins/kanban-bases-view`), `release_url(name)`, `installed_version(vault) -> str | None` (None for no copy or an unreadable manifest).
- `download(url) -> bytes`: `urllib.request.urlopen`, 30 s timeout.
- `install_plugin(vault, fetch, backups, *, home) -> str`: `"installed"`, `"present"` or `"failed: <why>"`. Reads `community-plugins.json` (must be a JSON list of strings), fetches all three files into a temp dir, checks the manifest version and every SHA-256, and only then backs up and overwrites the plugin folder (other files there, such as `data.json`, stay) and appends `PLUGIN_ID` to `community-plugins.json` through `files.write_json`.
- `VAULT_NAME`: the kebab-case regex `^[a-z0-9][a-z0-9-]*$`.

### `settings.py`

- Constants: `MARKETPLACE = "adhd-planner"`, `PLUGINS = ("planner", "tasks", "task-track")`, `VAULT_PLUGINS = ("tasks", "task-track")`, `OBSIDIAN_ALLOW = "Bash(obsidian:*)"`.
- `desired(vault, *, permissions) -> dict`: `pluginConfigs["<p>@adhd-planner"].options.vaultPath` for each of `VAULT_PLUGINS`, plus `permissions.allow` gets `Bash(obsidian:*)` when `permissions` is true.
- `merge(current, wanted, *, home) -> (merged, changes)`: merges into a deep copy. Change lines name keys, never values.
- `_child(parent, key, kind, label)`: gets `parent[key]`, creating it empty when missing (also used by `actions.py`).

### `paths.py`

- `GITHUB = "thetonymaster/adhd_planner"`, `NAME = "adhd-planner"`.
- `vault(env, home) -> Path`: `$VAULT`, else `~/vault`. It does not read `vaults.json` or settings.
- `vaults_file(env, home) -> Path`: `$ADHD_PLANNER_VAULTS`, else `~/.config/adhd-planner/vaults.json`.
- `tilde(path, home) -> str`, `norm(path, home) -> str`: `~` handling and normalisation used for path comparisons.
- `examples() -> Path`: the bundled `planner_setup/examples` (wheel), else `<repo>/examples` (checkout); raises `SystemExit` when neither exists.
- `find_checkout(direct_url, package_file)`, `checkout() -> Path | None`: the repo checkout setup was installed from (PEP 610 `direct_url.json`, or the source tree).
- `marketplace_source(checkout) -> str`: the checkout path when there is one, else `GITHUB`.

### `files.py`

- `load_json(path) -> dict`: `{}` for a missing or blank file.
- `backup_dir(home) -> Path`: a fresh `~/.claude/backups/<YYYYmmddHHMMSS>[-n]`.
- `backup(path, backups, *, home) -> Path | None`: copies `path` (a file, or a folder with `copytree`) under `backups`, keeping its path relative to home; a path outside home keeps only its name.
- `write_json(path, data: dict | list, backups, *, home) -> Path | None`: backup, then atomic write. Returns the backup path.

### `claude_cli.py`

- `Result(code, out, err)` NamedTuple; `available() -> bool` (is `claude` on PATH); `run(*args) -> Result`.

## Invariants

- **Confirm before writing.** Every writing action prints the planned change first, then writes only with `--yes` or a yes from `ctx.confirm`. `--dry-run` prints `Would ...` (`install`: `would run: claude ...`) and returns 0 without writing. Three writes in `update_vaults` are announced but not asked, as `docs/setup.md` describes: appending the board views to a `Tasks.base` (`added`), adding `priority` / `due` to `Templates/Task.md`, and enabling an already-pinned plugin copy in `community-plugins.json`. The questions are the plugin download and replacing a conflicting `Tasks.base`.
- **Exit codes.** 0 = done, nothing to do, or dry run; `status` also returns 0 when `claude` is missing or its state cannot be read. 1 = declined, `claude` failed (`install`), a board plugin install failed (`update_vaults`; `seed_vault` reports it and returns 0), a conflict, or a `SystemExit(<message>)` from a bad file (`files.load_json`, `settings._child`) or missing examples (`paths.examples()`), printed to stderr. 2 = invalid input (vault name not kebab-case, zone not an exact IANA name, `$ADHD_PLANNER_VAULTS` not absolute, menu without a TTY).
- **Bad files stop setup, unchanged.** Invalid JSON, a non-object top level, or a settings key of the wrong type raises `SystemExit` with a message ending "nothing was changed". Do not replace these with defaults.
- **Never clobber.** `seed_vault` leaves an existing path alone. `claude_md` keeps an existing `~/.claude/CLAUDE.md`. `merge` changes only the keys `desired` names and appends to permission lists without duplicates.
- **The board plugin is pinned by bytes.** `install_plugin` refuses files whose SHA-256 differs from `PLUGIN_SHA256` or whose manifest version is not `PLUGIN_VERSION`, and fetches and checks everything before the vault changes: every `failed:` result leaves the vault as it was.
- **Writes are atomic and backed up.** `write_json` backs up the old file first, writes a `mkstemp` temp beside the target with the target's mode (or `0666 & ~umask`), checks that the temp parses as JSON, then `replace`s. A symlinked settings file stays a link: the file it points at is written. `Tasks.base` and the plugin's files are backed up first but written in place (`write_bytes`, `copyfile`), not atomically.
- **Change lines never print the vault path.** `merge` reports `options.vaultPath: set|change` and, for `additionalDirectories`, `add vault`. `permissions.allow` entries are printed as is (`permissions.allow: add Bash(obsidian:*)`). `desired()` never sets `additionalDirectories`, so through `configure` only the `allow` line can appear.
- **`vaults.json` must stay loadable by the hooks.** Its rules are enforced in `plugins/tasks/hooks/vaults.py` and `plugins/task-track/hooks/resolve.ts`. `add_vault` and `set_timezone` keep it valid this way:
  - vault names are kebab-case;
  - the file path is absolute;
  - the first write also registers the current vault (`existing_name`, default `personal`) and sets it as `default`;
  - a file that would have two vaults gets a `default`;
  - folders are absolute and written with `~`, and a folder belongs to one vault only;
  - an existing vault name is refused.
- **Timezone check is exact.** `set_timezone` checks membership in `zoneinfo.available_timezones()`, not `ZoneInfo(...)`. On a case-insensitive disk, `ZoneInfo('asia/tokyo')` loads although the name is wrong.
- **Paths written for hooks are absolute.** `cli.py` expands `~` and calls `.absolute()` on vault paths, because hooks resolve them from any cwd.
- **`questionary` is imported only inside `_menu`.** Subcommands run without it on the import path.
- **The vault rules exist in three places.** `paths.vault` / `vaults_file` and `actions._current_vault` (settings `vaultPath`, else `$VAULT`, else `~/vault`) must stay in step with `plugins/tasks/hooks/vaults.py`, `plugins/task-track/hooks/resolve.ts` and `docs/setup.md`. `status` shows only this single-vault fallback; it does not read `vaults.json`.
- **Known gap: `vaults.json` shape is not checked.** Setup reads `vaults` with `current.get("vaults") or {}`: `null` or `[]` count as no vaults (the settings vault is used or seeded), and a non-empty list ends in a traceback (`update-vaults`: `AttributeError: 'list' object has no attribute 'items'`, exit 1). The hooks reject such a file at session start.

## Side Effects

- **Subprocess:** `claude plugin marketplace list|add`, `claude plugin list|install` (300 s timeout per call, exit 124 on timeout).
- **Network:** `board_plugin.download` fetches the three release assets from `https://github.com/xiwcx/obsidian-bases-kanban/releases/download/0.10.6/` (`seed_vault`, `update_vaults`).
- **Writes `~/.claude/settings.json`** (`configure`) and **`vaults.json`** (`add_vault`, `set_timezone`), each with a backup under `~/.claude/backups/<timestamp>/`.
- **Writes into vaults** (`seed_vault`, `update_vaults`): `<vault>/Tasks.base`, `<vault>/Templates/Task.md` (`update_vaults` only), `<vault>/.obsidian/plugins/kanban-bases-view/{manifest.json,main.js,styles.css}` and `<vault>/.obsidian/community-plugins.json`; `update_vaults` backs them up under `~/.claude/backups/<timestamp>/<vault name>/`.
- **Creates directories:** the starter vault tree (`seed_vault`, `shutil.copytree`), the plugin folder, a temp staging dir for downloads, and the parents of `~/.claude/CLAUDE.md` and of `vaults.json`.
- **Copies** `examples/CLAUDE.md` to `~/.claude/CLAUDE.md` (`claude_md`).
- **Reads** the environment (`VAULT`, `ADHD_PLANNER_VAULTS`), `Path.home()`, `Path.cwd()`, and package metadata (`direct_url.json`).
- **Terminal I/O:** prints through `ctx.say`, which is `print` in the CLI, and prompts through `input` or `questionary`.

## Verification

- Run: `cd setup && uv run pytest` (tests in `setup/tests/`: `test_actions.py`, `test_board_plugin.py`, `test_cli.py`, `test_files.py`, `test_settings.py`; tests pass a fake `fetch` or use `--dry-run`, so none downloads; `test_board_plugin.py` checks the starter `Tasks.base` holds both views verbatim).
- Single test: `cd setup && uv run pytest tests/test_cli.py -k <name>`.
