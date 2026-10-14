import json
import os
import stat
from pathlib import Path

import pytest

from planner_setup.actions import Ctx

FAKE = """#!/usr/bin/env python3
import json, os, sys, pathlib
d = pathlib.Path(os.environ["FAKE_CLAUDE_DIR"])
with open(d / "calls.jsonl", "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
key = "_".join(a for a in sys.argv[1:] if not a.startswith("-")).replace("/", "_")[:60]
reply = d / f"{key}.json"
if reply.exists():
    r = json.loads(reply.read_text())
    sys.stdout.write(r.get("out", "")); sys.stderr.write(r.get("err", "")); sys.exit(r.get("code", 0))
sys.stdout.write("[]" if "--json" in sys.argv else "")
"""


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    d = tmp_path / "fakebin"
    d.mkdir()
    exe = d / "claude"
    exe.write_text(FAKE)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{d}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_DIR", str(d))

    class Fake:
        dir = d
        def reply(self, key, out="", err="", code=0):
            (d / f"{key}.json").write_text(json.dumps({"out": out, "err": err, "code": code}))
        def calls(self):
            p = d / "calls.jsonl"
            return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
    return Fake()


@pytest.fixture
def ctx(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    lines: list[str] = []
    c = Ctx(home=home, cwd=tmp_path, env={}, yes=True, dry_run=False,
            confirm=lambda _q: True, say=lines.append)
    c.lines = lines  # type: ignore[attr-defined]
    return c
