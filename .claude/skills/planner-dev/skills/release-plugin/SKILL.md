---
name: release-plugin
description: Ready this repo's changed plugins for a PR — bump versions, run every check that covers them, rebuild planner.plugin. Run with /planner-dev:release-plugin before opening a PR.
disable-model-invocation: true
---

# Release the changed plugins

Work from the repo root. Report each step's outcome as observed; stop at the first failure and show its raw output.

1. **What changed.** `git diff --name-only main...HEAD` plus `git status --short`. Group paths by plugin (`plugins/<name>/…`, and the repo-local `.claude/skills/<name>/…`); note `setup/`, `tests/`, `scripts/`, root `*.html` separately.
2. **Versions.** For each changed plugin under `plugins/` (repo-local ones aren't installed anywhere, so their version isn't bumped), compare `version` in `plugins/<name>/.claude-plugin/plugin.json` with `git show main:plugins/<name>/.claude-plugin/plugin.json`. If unchanged, propose a bump (patch for fixes/docs, minor for new skills, commands or options) and apply it after Q confirms.
3. **Checks.** Run only those covering what changed; print one line each, `VERIFY: Ran <command> — Result: PASS|FAIL|DID NOT RUN`.

   | Changed | Command |
   |---|---|
   | any plugin under `plugins/` | `claude plugin validate plugins/<name>` |
   | `plugins/tasks/` or `tests/` | `python3 -m unittest discover -s tests` |
   | `plugins/task-track/` | `cd plugins/task-track && claude plugin test .` |
   | `.claude/skills/planner-dev/` | `claude plugin validate .claude/skills/planner-dev` and `cd .claude/skills/planner-dev && claude plugin test .` |
   | `setup/`, `examples/`, `docs/setup.md` | `cd setup && uv run pytest` |
   | root `*.html` or `scripts/` | `node --test scripts/` and `node scripts/lint-pages.mjs *.html` |

   Vault-resolution changes (`vaults.py`, `session_task.py`, `resolve.ts`) need both the Python and the task-track suite, whichever side changed.
4. **Build.** If `plugins/planner/` changed: `bash scripts/build-plugin.sh`, then confirm `git status` shows `planner.plugin` modified.
5. **Docs.** If a plugin option, a vault rule or an install step changed, check `docs/setup.md` and the plugin's README say the same; list any mismatch, don't fix it unasked.
6. **Report.** The VERIFY lines, the version bumps, and the files ready to stage (named individually). Do not commit or push.
