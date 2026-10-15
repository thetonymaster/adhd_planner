"""Where things are: the vault, the bundled examples, the marketplace source."""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote, urlparse

GITHUB = "thetonymaster/adhd_planner"
NAME = "adhd-planner"


def vault(env: Mapping[str, str], home: Path) -> Path:
    raw = env.get("VAULT") or "~/vault"
    return Path(str(home) + raw[1:]) if raw == "~" or raw.startswith("~/") else Path(raw)


def vaults_file(env: Mapping[str, str], home: Path) -> Path:
    """The vault registry the hooks and the mod read (plugins/tasks/hooks/vaults.py)."""
    raw = env.get("ADHD_PLANNER_VAULTS")
    return Path(norm(raw, home)) if raw else home / ".config" / "adhd-planner" / "vaults.json"


def tilde(path: Path, home: Path) -> str:
    """`path` with `~` for home, the way vaults.json and `repo:` write paths."""
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)


def norm(path: str, home: Path | str) -> str:
    """`~` → home, then normalised (no trailing slash, no `..`), for comparing paths as written."""
    if path == "~" or path.startswith("~/"):
        path = str(home) + path[1:]
    return os.path.normpath(path)


def examples() -> Path:
    bundled = Path(__file__).resolve().parent / "examples"
    if bundled.is_dir():
        return bundled
    checkout = Path(__file__).resolve().parents[3] / "examples"  # setup/src/planner_setup → repo
    if checkout.is_dir():
        return checkout
    raise SystemExit(f"examples/ not found (looked in {bundled} and {checkout}); reinstall planner-setup.")


def _is_marketplace(root: Path) -> bool:
    try:
        return json.loads((root / ".claude-plugin" / "marketplace.json").read_text()).get("name") == NAME
    except (OSError, ValueError):
        return False


def find_checkout(direct_url: str | None, package_file: Path) -> Path | None:
    """The repo checkout planner-setup was installed from, else None.

    `direct_url` is the PEP 610 direct_url.json text; `uvx --from ./setup` and editable
    installs record a file:// URL to setup/ there. `package_file` covers running from
    the source tree. A candidate counts only if it holds this marketplace's manifest.
    """
    candidates = []
    try:
        url = json.loads(direct_url).get("url", "") if direct_url else ""
    except ValueError:
        url = ""
    if url.startswith("file://"):
        url_dir = Path(unquote(urlparse(url).path))
        candidates += [url_dir, url_dir.parent]  # repo root with subdirectory="setup", or setup/ itself
    candidates.append(package_file.resolve().parents[3])  # setup/src/planner_setup/paths.py → repo
    return next((c for c in candidates if _is_marketplace(c)), None)


def checkout() -> Path | None:
    try:
        direct_url = metadata.distribution("planner-setup").read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        direct_url = None
    return find_checkout(direct_url, Path(__file__))


def marketplace_source(checkout: Path | None) -> str:
    return str(checkout) if checkout else GITHUB
