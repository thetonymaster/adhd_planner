"""The seven things setup can do. Each returns an exit code and talks through ctx.say."""
from __future__ import annotations

import json
import re
import shutil
import zoneinfo
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import claude_cli, files, paths, settings

VAULT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass
class Ctx:
    home: Path
    cwd: Path
    env: Mapping[str, str]
    yes: bool
    dry_run: bool
    confirm: Callable[[str], bool]
    say: Callable[[str], None]
    checkout: Path | None = None

    @property
    def settings_path(self) -> Path:
        return self.home / ".claude" / "settings.json"


def _json(ctx: Ctx, *args: str) -> list | None:
    r = claude_cli.run(*args, "--json")
    if r.code != 0:
        ctx.say(f"`claude {' '.join(args)} --json` failed (exit {r.code}): {r.err.strip()}")
        return None
    try:
        return json.loads(r.out or "[]")
    except ValueError as err:
        ctx.say(f"`claude {' '.join(args)} --json` printed non-JSON ({err}): {r.out[:200]!r}")
        return None


def _state(ctx: Ctx) -> tuple[bool, dict[str, bool]] | None:
    """(marketplace added, {plugin: enabled}) or None if claude could not be asked."""
    markets = _json(ctx, "plugin", "marketplace", "list")
    plugins = _json(ctx, "plugin", "list")
    if markets is None or plugins is None:
        return None
    added = any(m.get("name") == settings.MARKETPLACE for m in markets)
    suffix = "@" + settings.MARKETPLACE
    installed = {p["id"][: -len(suffix)]: bool(p.get("enabled")) for p in plugins if p.get("id", "").endswith(suffix)}
    return added, installed


def _current_vault(ctx: Ctx, current: dict) -> tuple[Path, bool]:
    """Today's vault: the tasks plugin's vaultPath in settings.json, else $VAULT, else ~/vault; and whether settings named it."""
    tasks_id = f"tasks@{settings.MARKETPLACE}"
    configs = settings._child(current, "pluginConfigs", dict, "pluginConfigs")
    options = settings._child(settings._child(configs, tasks_id, dict, f"pluginConfigs.{tasks_id}"),
                              "options", dict, f"pluginConfigs.{tasks_id}.options")
    configured = options.get("vaultPath")
    if configured:
        return Path(paths.norm(configured, ctx.home)), True
    return paths.vault(ctx.env, ctx.home), False


def _absolute(ctx: Ctx, written: str) -> Path:
    """`written` with `~` expanded and a relative path taken from where setup runs, normalised."""
    return Path(paths.norm(str(ctx.cwd / paths.norm(written, ctx.home)), ctx.home))


def status(ctx: Ctx) -> int:
    if not claude_cli.available():
        ctx.say("claude: not found on PATH (plugin state unknown)")
    else:
        state = _state(ctx)
        if state is not None:
            added, installed = state
            ctx.say(f"marketplace {settings.MARKETPLACE}: {'added' if added else 'not added'}")
            for p in settings.PLUGINS:
                ctx.say(f"  {p}: " + ("not installed" if p not in installed
                                      else "enabled" if installed[p] else "installed, disabled"))
    current = files.load_json(ctx.settings_path)
    vault, configured = _current_vault(ctx, current)
    ctx.say(f"vault: {vault} ({'exists' if vault.is_dir() else 'missing'}; {'from settings' if configured else 'default'})")
    dirs = settings._child(settings._child(current, "permissions", dict, "permissions"),
                           "additionalDirectories", list, "permissions.additionalDirectories")
    listed = any(paths.norm(d, ctx.home) == paths.norm(str(vault), ctx.home) for d in dirs if isinstance(d, str))
    ctx.say("vault in additionalDirectories: " + (
        "yes (not needed; edits there may skip the tasks hook's write rules: consider removing it)"
        if listed else "no (the tasks hook approves note reads and writes per call)"))
    return 0


def install(ctx: Ctx, plugins: Sequence[str]) -> int:
    if not claude_cli.available():
        ctx.say("claude: not found on PATH. Install Claude Code, then rerun.")
        return 1
    state = _state(ctx)
    if state is None:
        return 1
    added, installed = state
    steps: list[tuple[str, ...]] = []
    if not added:
        steps.append(("plugin", "marketplace", "add", paths.marketplace_source(ctx.checkout)))
    steps += [("plugin", "install", f"{p}@{settings.MARKETPLACE}") for p in plugins if p not in installed]
    if not steps:
        ctx.say("Nothing to install: marketplace and plugins are already there.")
        return 0
    for s in steps:
        ctx.say(("would run: " if ctx.dry_run else "run: ") + "claude " + " ".join(s))
    if ctx.dry_run or not (ctx.yes or ctx.confirm("Run these?")):
        return 0 if ctx.dry_run else 1
    for s in steps:
        r = claude_cli.run(*s)
        if r.code != 0:
            ctx.say(f"`claude {' '.join(s)}` failed (exit {r.code}):\n{r.err.strip() or r.out.strip()}")
            return 1
    ctx.say("Done. Start a new `claude` session to load the plugins.")
    return 0


def configure(ctx: Ctx, vault: Path, permissions: bool) -> int:
    current = files.load_json(ctx.settings_path)
    merged, changes = settings.merge(current, settings.desired(str(vault), permissions=permissions), home=str(ctx.home))
    if not changes:
        ctx.say(f"Nothing to change in {ctx.settings_path}.")
        return 0
    ctx.say(("Would change " if ctx.dry_run else "Will change ") + f"{ctx.settings_path}:")
    for c in changes:
        ctx.say(f"  - {c}")
    if ctx.dry_run:
        return 0
    if not (ctx.yes or ctx.confirm("Write these changes?")):
        ctx.say("Nothing written.")
        return 1
    saved = files.write_json(ctx.settings_path, merged, files.backup_dir(ctx.home), home=ctx.home)
    if saved:
        ctx.say(f"Backup: {saved}")
    ctx.say("Done. Running sessions pick this up after a restart.")
    return 0


def seed_vault(ctx: Ctx, vault: Path) -> int:
    if vault.exists():
        ctx.say(f"{vault} already exists; left as is.")
        return 0
    ctx.say(("Would create " if ctx.dry_run else "Create ") + f"a starter vault at {vault}")
    if ctx.dry_run or not (ctx.yes or ctx.confirm("Create it?")):
        return 0 if ctx.dry_run else 1
    shutil.copytree(paths.examples() / "vault-starter", vault)
    (vault / "_claude").rename(vault / ".claude")
    ctx.say(f"Vault created at {vault}. Open it in Obsidian: Open folder as vault.")
    return 0


def add_vault(ctx: Ctx, name: str, path: Path, folders: Sequence[str], existing_name: str = "personal") -> int:
    """Registers another vault in vaults.json. The first time, today's vault goes in too, as the default."""
    for n in (name, existing_name):
        if not VAULT_NAME.match(n):
            ctx.say(f"Vault name {n!r} must be kebab-case (a-z, 0-9, -); nothing was changed.")
            return 2
    target = paths.vaults_file(ctx.env, ctx.home)
    if not target.is_absolute():
        # The hooks would read it relative to each session's folder: a different file per repo.
        ctx.say(f"$ADHD_PLANNER_VAULTS must be an absolute path or start with ~/, got {str(target)!r}; nothing was changed.")
        return 2
    current = files.load_json(target)
    vaults = dict(current.get("vaults") or {})
    if not vaults:
        seed, _ = _current_vault(ctx, files.load_json(ctx.settings_path))
        vaults[existing_name] = {"path": paths.tilde(_absolute(ctx, str(seed)), ctx.home)}
        current["default"] = existing_name
    elif "default" not in current and len(vaults) == 1:
        # One vault needs no default; two do, or the hooks reject the file.
        current["default"] = next(iter(vaults))
    if name in vaults:
        ctx.say(f"{target} already has a vault named {name!r} ({vaults[name].get('path')}); nothing was changed.")
        return 1
    # The hooks reject the whole file for a relative folder or one listed under two vaults.
    resolved = [_absolute(ctx, f) for f in folders]
    owners = {_absolute(ctx, f): n for n, spec in vaults.items() if isinstance(spec, dict)
              for f in spec.get("folders") or [] if isinstance(f, str)}
    for folder in resolved:
        if folder in owners:
            ctx.say(f"{paths.tilde(folder, ctx.home)} is already in {owners[folder]!r}'s folders in {target}; "
                    f"a folder belongs to one vault only. Move it there by hand; nothing was changed.")
            return 1
    entry: dict = {"path": paths.tilde(path, ctx.home)}
    if folders:
        entry["folders"] = [paths.tilde(f, ctx.home) for f in resolved]
    merged = {**current, "vaults": {**vaults, name: entry}}
    if not (path / "Tasks").is_dir():
        ctx.say(f"{path} has no Tasks/ yet: sessions skip this vault until it has one.")
    ctx.say(("Would write " if ctx.dry_run else "Will write ") + f"{target}:\n{json.dumps(merged, indent=2)}")
    if ctx.dry_run:
        return 0
    if not (ctx.yes or ctx.confirm("Write it?")):
        return 1
    files.write_json(target, merged, files.backup_dir(ctx.home), home=ctx.home)
    ctx.say(f"Wrote {target}. New sessions see vault {name!r}; /tasks:task-switch {name}:<slug> moves a session there.")
    return 0


def set_timezone(ctx: Ctx, zone: str, existing_name: str = "personal") -> int:
    """Sets vaults.json's `timezone`, which the hooks and task-track stamp times in. No file yet: today's vault goes in."""
    # The exact-name set, as the hooks check it: ZoneInfo alone takes 'asia/tokyo' on macOS, whose disk ignores case.
    if zone not in zoneinfo.available_timezones():
        ctx.say(f"{zone!r} is not an IANA zone (e.g. America/Mexico_City); nothing was changed.")
        return 2
    target = paths.vaults_file(ctx.env, ctx.home)
    if not target.is_absolute():
        ctx.say(f"$ADHD_PLANNER_VAULTS must be an absolute path or start with ~/, got {str(target)!r}; nothing was changed.")
        return 2
    current = files.load_json(target)
    if not current.get("vaults"):
        seed, _ = _current_vault(ctx, files.load_json(ctx.settings_path))
        current = {**current, "default": existing_name,
                   "vaults": {existing_name: {"path": paths.tilde(_absolute(ctx, str(seed)), ctx.home)}}}
    merged = {**current, "timezone": zone}
    ctx.say(("Would write " if ctx.dry_run else "Will write ") + f"{target}:\n{json.dumps(merged, indent=2)}")
    if ctx.dry_run:
        return 0
    if not (ctx.yes or ctx.confirm("Write it?")):
        return 1
    files.write_json(target, merged, files.backup_dir(ctx.home), home=ctx.home)
    ctx.say(f"Wrote {target}. New sessions stamp times in {zone}.")
    return 0


def claude_md(ctx: Ctx) -> int:
    example = paths.examples() / "CLAUDE.md"
    target = ctx.home / ".claude" / "CLAUDE.md"
    if target.exists():
        ctx.say(f"{target} exists; kept your file. Compare with: diff {target} {example}")
        return 0
    ctx.say(("Would copy " if ctx.dry_run else "Copy ") + f"{example} → {target}")
    if ctx.dry_run or not (ctx.yes or ctx.confirm("Copy it?")):
        return 0 if ctx.dry_run else 1
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(example, target)
    ctx.say("Copied. Edit it to fit how you work.")
    return 0


def cowork(ctx: Ctx) -> int:
    ctx.say("\n".join([
        "In Claude Desktop → Cowork:",
        f"  1. Customize → Plugins → Add marketplace → {paths.GITHUB}",
        "  2. Install `planner` and `tasks` (task-track is Claude Code only).",
        "  3. Connect your vault folder to the session.",
        '  4. Try: "add a note to <task>: test".',
        "If adding the marketplace fails, see setup.md → Cowork fallback.",
    ]))
    return 0
