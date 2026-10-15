"""planner-setup: a menu (no arguments) or subcommands over the same actions."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import actions, paths, settings

MENU = ("Status", "Install plugins (Claude Code)", "Settings (vault path, permissions)",
        "Vault starter", "Add another vault", "Example CLAUDE.md", "Cowork steps", "Quit")


def _ctx(args: argparse.Namespace, confirm=None) -> actions.Ctx:
    return actions.Ctx(home=Path.home(), cwd=Path.cwd(), env=os.environ, yes=args.yes, dry_run=args.dry_run,
                       confirm=confirm or (lambda q: input(f"{q} [y/N] ").strip().lower() == "y"), say=print)


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="planner-setup", description=__doc__)
    ap.add_argument("--yes", action="store_true", help="do not ask before writing")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    p = sub.add_parser("install")
    p.add_argument("--plugins", nargs="+", choices=settings.PLUGINS, default=list(settings.PLUGINS))
    p = sub.add_parser("settings")
    p.add_argument("--vault", type=Path)
    p.add_argument("--permissions", action="store_true", help="also allow Bash(obsidian:*)")
    p = sub.add_parser("vault")
    p.add_argument("--vault", type=Path)
    p = sub.add_parser("add-vault", help="register another vault in ~/.config/adhd-planner/vaults.json")
    p.add_argument("name", help="kebab-case, e.g. work")
    p.add_argument("--path", type=Path, required=True)
    p.add_argument("--folder", action="append", default=[], help="a folder whose sessions use this vault (repeatable)")
    p.add_argument("--existing-name", default="personal", help="name for today's vault when the file is created")
    sub.add_parser("claude-md")
    sub.add_parser("cowork")
    return ap


def _menu(args: argparse.Namespace) -> int:
    import questionary  # only the menu needs it

    ctx = _ctx(args, confirm=lambda q: bool(questionary.confirm(q, default=False).ask()))
    default_vault = str(paths.vault(os.environ, Path.home()))
    while True:
        choice = questionary.select("planner-setup", choices=list(MENU)).ask()
        if choice in (None, "Quit"):
            return 0
        if choice == "Status":
            actions.status(ctx)
        elif choice.startswith("Install"):
            picked = questionary.checkbox("Plugins", choices=[
                questionary.Choice(p, checked=True) for p in settings.PLUGINS]).ask() or []
            actions.install(ctx, picked)
        elif choice.startswith("Settings"):
            vault = questionary.path("Vault path", default=default_vault, only_directories=True).ask()
            if vault:
                perms = bool(questionary.confirm("Also allow Bash(obsidian:*)?",
                                                 default=False).ask())
                actions.configure(ctx, Path(os.path.expanduser(vault)).absolute(), perms)
        elif choice == "Vault starter":
            vault = questionary.path("Create the starter vault at", default=default_vault).ask()
            if vault:
                actions.seed_vault(ctx, Path(os.path.expanduser(vault)).absolute())
        elif choice == "Add another vault":
            name = questionary.text("Name (kebab-case, e.g. work)").ask()
            where = questionary.path("Vault path", only_directories=True).ask()
            folders = questionary.text("Folders whose sessions use it (comma-separated, optional)").ask() or ""
            if name and where:
                actions.add_vault(ctx, name.strip(), Path(os.path.expanduser(where)).absolute(),
                                  [f.strip() for f in folders.split(",") if f.strip()])
        elif choice == "Example CLAUDE.md":
            actions.claude_md(ctx)
        elif choice == "Cowork steps":
            actions.cowork(ctx)
        print()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd is None:
        if not sys.stdin.isatty():
            print("planner-setup: no terminal for the menu; pass a subcommand (see --help).", file=sys.stderr)
            return 2
        return _menu(args)
    ctx = _ctx(args)
    vault = getattr(args, "vault", None) or paths.vault(os.environ, ctx.home)
    vault = Path(os.path.expanduser(str(vault))).absolute()  # hooks resolve it from any cwd
    return {
        "status": lambda: actions.status(ctx),
        "install": lambda: actions.install(ctx, args.plugins),
        "settings": lambda: actions.configure(ctx, vault, args.permissions),
        "vault": lambda: actions.seed_vault(ctx, vault),
        "add-vault": lambda: actions.add_vault(ctx, args.name, Path(os.path.expanduser(str(args.path))).absolute(),
                                               args.folder, args.existing_name),
        "claude-md": lambda: actions.claude_md(ctx),
        "cowork": lambda: actions.cowork(ctx),
    }[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())
