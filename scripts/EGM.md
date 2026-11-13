# scripts

## Overview

Repo maintenance scripts. One script today: `build-plugin.sh`, which builds
`planner.plugin` at the repo root, the zip of `plugins/planner` that users
upload to Cowork (Customize → Plugins). `planner.plugin` is committed and is a
build output: it changes only through this script, never by hand.

## Interface

- `build-plugin.sh`: run as `bash scripts/build-plugin.sh` from any directory.
  It takes no arguments and resolves the repo root as the parent of `scripts/`.
  It reads `plugins/planner/` and `tests/`, and writes `planner.plugin` at the repo root.
  Steps, in order:
  1. `claude plugin validate plugins/planner`
  2. `python3 -m unittest discover -s tests` (the whole Python suite, not only
     planner tests: it also covers the `tasks` hooks such as `vault-allow.py`,
     `load-task.sh` and `park_on_end.py`, and the skill-file checks)
  3. Lists every file under `plugins/planner`, sorted, excluding `.DS_Store`,
     `EGM.md`, `__pycache__/`, `*.pyc` and `tools/out/` (`task_queue.py` output), and zips them with `zip -X` (no extra file
     attributes) into a temp dir.
  4. `unzip -tq` integrity check, then diffs the zip listing against the
     file list; any difference aborts with `zip contents differ from <src>`.
  5. Reads the file count and `version` from
     `plugins/planner/.claude-plugin/plugin.json` into variables.
  6. Moves the zip to `planner.plugin` and prints
     `Built <path> (<N> files, version <v>)`.
- Callers: `AGENTS.md`, `README.md`, `docs/setup.md`, the repo-local
  `release-plugin` skill
  (`.claude/skills/planner-dev/skills/release-plugin/SKILL.md`, step 4), and the
  planner-dev guard's deny message (`.claude/skills/planner-dev/hooks/register.ts`),
  which points edits of `planner.plugin` at this script.

## Invariants

- Fail-closed: `set -euo pipefail`. Any failed validate, test, zip, diff or
  version-read step exits before the final `mv`, so the previous `planner.plugin`
  stays as it was (a `plugin.json` without `version` exits 1 with it unchanged).
  The count and version are read before the `mv` on purpose: a failure inside the
  closing `echo`'s `$(...)` would not stop the script. The temp dir is removed on
  exit by a `trap`.
- Archive paths are relative to `plugins/planner` (no `plugins/planner/`
  prefix): the plugin root is the zip root.
- The zip holds exactly the source tree minus the four exclusions. Add new
  patterns to both the `find` filter and this doc, or they ship. `EGM.md` is
  excluded so the repo's contract files never reach users.
- Rebuild whenever `plugins/planner/` changes, and bump `version` in
  `plugins/planner/.claude-plugin/plugin.json` first so the printed version and
  the shipped manifest match.
- `planner.plugin` is edit-denied by the planner-dev guard
  (`.claude/skills/planner-dev/hooks/register.ts`). Only this script may change it.
- Required tools on `PATH`: `claude`, `python3`, `zip`, `unzip`, `diff`,
  `find`, `sed`, `sort`, `mktemp`, `wc`, `tr`, `dirname`, `mv`, `rm`.
- The header comment names `plugins/planner/` and lists the steps above (validate,
  run `tests/`, zip minus `EGM.md`, caches and `tools/out/`, check, read the version, move); keep
  it in step with the code.

## Side Effects

- Overwrites `<repo>/planner.plugin`, a tracked file. Whether it shows as
  modified with no source change is unverified: `zip -X` stores file mtimes and
  no archive timestamp, so an unchanged tree may rebuild byte-identical.
- Runs the full `tests/` unittest suite, with whatever side effects those tests
  have.
- Creates and deletes a `mktemp -d` directory.
- The script makes no network calls of its own. Whether `claude plugin validate`
  touches the network has not been verified.

## Verification

- Run: `python3 -m unittest discover -s tests` (no side effects on the repo)
- Run: `bash scripts/build-plugin.sh` (rewrites `planner.plugin`; check that
  `git status` shows only that file changed)
- Read-only check that the committed `planner.plugin` matches the source tree:
  `(cd plugins/planner && find . -type f ! -name '.DS_Store' ! -name 'EGM.md' ! -path '*/__pycache__/*' ! -path './tools/out/*' ! -name '*.pyc' | sed 's|^\./||' | sort) | diff - <(unzip -Z1 planner.plugin | sort)`
  (no output = same file list)
