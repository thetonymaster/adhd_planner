"""The `claude` CLI, as a function returning what it printed."""
from __future__ import annotations

import shutil
import subprocess
from typing import NamedTuple


class Result(NamedTuple):
    code: int
    out: str
    err: str


def available() -> bool:
    return shutil.which("claude") is not None


def run(*args: str) -> Result:
    try:
        p = subprocess.run(["claude", *args], capture_output=True, text=True, timeout=300, check=False)
    except subprocess.TimeoutExpired:
        return Result(124, "", f"claude {' '.join(args)} timed out after 300s")
    return Result(p.returncode, p.stdout, p.stderr)
