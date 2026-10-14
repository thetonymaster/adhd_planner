"""The six things setup can do. Each returns an exit code and talks through ctx.say."""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import claude_cli, files, paths, settings


@dataclass
class Ctx:
    home: Path
    cwd: Path
    env: Mapping[str, str]
    yes: bool
    dry_run: bool
    confirm: Callable[[str], bool]
    say: Callable[[str], None]

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
    tasks_id = f"tasks@{settings.MARKETPLACE}"
    configs = settings._child(current, "pluginConfigs", dict, "pluginConfigs")
    options = settings._child(settings._child(configs, tasks_id, dict, f"pluginConfigs.{tasks_id}"),
                              "options", dict, f"pluginConfigs.{tasks_id}.options")
    configured = options.get("vaultPath")
    vault = Path(paths.norm(configured, ctx.home)) if configured else paths.vault(ctx.env, ctx.home)
    ctx.say(f"vault: {vault} ({'exists' if vault.is_dir() else 'missing'}; {'from settings' if configured else 'default'})")
    dirs = settings._child(settings._child(current, "permissions", dict, "permissions"),
                           "additionalDirectories", list, "permissions.additionalDirectories")
    listed = any(paths.norm(d, ctx.home) == paths.norm(str(vault), ctx.home) for d in dirs if isinstance(d, str))
    ctx.say(f"vault in additionalDirectories: {'yes' if listed else 'no (the tasks hook approves vault access per session)'}")
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
        steps.append(("plugin", "marketplace", "add", paths.marketplace_source(ctx.cwd)))
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
    ctx.say("Copied. Edit it: it is written for one person (Q).")
    return 0


def cowork(ctx: Ctx) -> int:
    ctx.say("\n".join([
        "In Claude Desktop → Cowork:",
        f"  1. Customize → Plugins → Add marketplace → {paths.GITHUB}",
        "  2. Install `planner` and `tasks` (task-track is Claude Code only).",
        "  3. Connect your vault folder to the session.",
        '  4. Try: "add a note to <task>: test".',
        "If adding the marketplace fails (private repo), see setup.md → Cowork fallback.",
    ]))
    return 0
