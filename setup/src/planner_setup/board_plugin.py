"""The community Obsidian plugin that renders the task board, and the Tasks.base views that use it.

Kanban Bases View (xiwcx/obsidian-bases-kanban, MIT): registers the Bases view type
`kanban-view`; view options `groupByProperty`, `cardTitleProperty` (default: file name) and
`columnOrders` ({propertyId: [values]}) are read from the view's entry in the .base file.
Dragging a card rewrites the grouped property in the note's frontmatter.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

from . import files

PLUGIN_ID = "kanban-bases-view"
PLUGIN_VERSION = "0.10.6"
PLUGIN_REPO = "xiwcx/obsidian-bases-kanban"
PLUGIN_FILES = ("manifest.json", "main.js", "styles.css")

# 7 days including today, matching /board in task-track.
DONE_WINDOW = 'finished >= today() - "6 days"'

BOARD_VIEW = f"""\
  - type: kanban-view
    name: Board
    filters:
      or:
        - status != "done"
        - {DONE_WINDOW}
    groupByProperty: note.status
    columnOrders:
      note.status:
        - parked
        - active
        - done
    order:
      - up
      - started
"""

DONE_VIEW_NAME = "Done (7 days)"

DONE_VIEW = f"""\
  - type: table
    name: {DONE_VIEW_NAME}
    filters:
      and:
        - status == "done"
        - {DONE_WINDOW}
    order:
      - file.name
      - up
      - finished
    sort:
      - property: finished
        direction: DESC
"""


def _view_name(lines: list[str]) -> str | None:
    for line in lines:
        m = re.match(r"(?:  - |    )name:\s*(.*?)\s*$", line)
        if m:
            name = m.group(1)
            return name[1:-1] if len(name) > 1 and name[0] == name[-1] and name[0] in "'\"" else name
    return None


def merge_base(text: str) -> tuple[str, str]:
    """Appends BOARD_VIEW and DONE_VIEW to a Tasks.base's `views:`, line by line, so every other view, sort and
    comment stays as written. "unchanged" when both are there verbatim; "conflict" (text untouched) when a view
    has one of their names but other text, or `views:` is not a block list at the starter's 2-space indent."""
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[-1] == "":
        lines.pop()
    start = next((i for i, line in enumerate(lines) if re.match(r"views:\s*(#.*)?$", line)), None)
    if start is None:
        return text, "conflict"
    end = next((j for j in range(start + 1, len(lines)) if re.match(r"[^\s#-]", lines[j])), len(lines))
    content = [j for j in range(start + 1, end) if lines[j].strip() and not lines[j].lstrip().startswith("#")]
    if content and (not lines[content[0]].startswith("  - ")
                    or any(not lines[j].startswith(("  - ", "    ")) for j in content)):
        return text, "conflict"
    last = content[-1] if content else start
    heads = [j for j in content if lines[j].startswith("  - ")]
    existing = {}
    for head, nxt in zip(heads, heads[1:] + [last + 1]):
        item = lines[head:nxt]
        while item and not item[-1].strip():
            item.pop()
        existing[_view_name(item)] = "\n".join(item) + "\n"
    missing = []
    for view in (BOARD_VIEW, DONE_VIEW):
        name = _view_name(view.splitlines())
        if name not in existing:
            missing.append(view)
        elif existing[name] != view:
            return text, "conflict"
    if not missing:
        return text, "unchanged"
    merged = lines[: last + 1] + "".join(missing).splitlines() + lines[last + 1:]
    return ("\n".join(merged) + "\n").replace("\n", eol), "added"


def plugin_dir(vault: Path) -> Path:
    return vault / ".obsidian" / "plugins" / PLUGIN_ID


def release_url(name: str) -> str:
    return f"https://github.com/{PLUGIN_REPO}/releases/download/{PLUGIN_VERSION}/{name}"


def installed_version(vault: Path) -> str | None:
    """The version in the vault's copy of the plugin; None when there is none or its manifest is unreadable."""
    manifest = plugin_dir(vault) / "manifest.json"
    if not manifest.exists():
        return None
    try:
        return json.loads(manifest.read_text()).get("version")
    except (ValueError, AttributeError):
        return None  # a broken copy: install_plugin replaces it, after a backup


def download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def install_plugin(vault: Path, fetch: Callable[[str], bytes], backups: Path, *, home: Path) -> str:
    """Puts the pinned release in <vault>/.obsidian/plugins/<id>/ and enables it in community-plugins.json.

    Every file is fetched before anything in the vault changes; a failed fetch leaves the vault as it was.
    Files the plugin keeps beside its own (data.json: its settings) survive an upgrade.
    Returns "installed", "present" (this version was already there) or "failed: <why>".
    """
    registry = vault / ".obsidian" / "community-plugins.json"
    raw = registry.read_text() if registry.exists() else ""
    try:
        enabled = json.loads(raw) if raw.strip() else []
    except ValueError as err:
        return f"failed: {registry} is not valid JSON ({err})"
    if not isinstance(enabled, list) or not all(isinstance(p, str) for p in enabled):
        return f"failed: {registry} holds {raw.strip()[:80]!r}, expected a JSON list of plugin ids"
    present = installed_version(vault) == PLUGIN_VERSION
    if not present:
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp)
            for name in PLUGIN_FILES:
                url = release_url(name)
                try:
                    (staged / name).write_bytes(fetch(url))
                except OSError as err:  # urllib's URLError, HTTPError and timeouts are all OSErrors
                    return f"failed: could not download {url} ({err})"
            try:
                got = json.loads((staged / "manifest.json").read_text()).get("version")
            except (ValueError, AttributeError) as err:
                return f"failed: {release_url('manifest.json')} is not a plugin manifest ({err})"
            if got != PLUGIN_VERSION:
                return f"failed: {release_url('manifest.json')} says version {got!r}, expected {PLUGIN_VERSION}"
            dest = plugin_dir(vault)
            files.backup(dest, backups, home=home)
            dest.mkdir(parents=True, exist_ok=True)
            for name in PLUGIN_FILES:
                shutil.copyfile(staged / name, dest / name)
    if PLUGIN_ID not in enabled:
        files.write_json(registry, [*enabled, PLUGIN_ID], backups, home=home)
    return "present" if present else "installed"
