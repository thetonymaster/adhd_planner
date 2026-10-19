# Vault timezone — plan

Spec: `docs/superpowers/specs/2026-10-16-vault-timezone-design.md`. Written after the chunks
below were built, test-first, one at a time; it records what each chunk did and how it was checked.

1. **Parse** — `timezone` and `warning` on the config in `vaults.py` and `resolve.ts` (same
   messages); `Vault config warning:` line in `session_task.py`; the mod adds the warning to its
   config-problem text. Four shared fixture cases (zone set ×2, unknown zone, non-string), checked
   by both runners. Check: `tests.test_load_task.SharedVaultCasesTest`, `tests.test_vaults`,
   task-track suite.
2. **Stamps** — `stamp(d, timeZone)` via `Intl` (`h23`); `zoneFor(config, $TZ)`; `load()` sets
   `zone` with `vault`; every call site (`addLog`, `today`, `flushFocus`, the pane's today,
   `blockSummary`/`logSince`) passes it. Check: stamp in two zones and at 00:05, zoneFor order,
   logSince, `/note` under a vaults.json zone and under `$TZ` only.
3. **`Now:` lines** — `vaults.zone_for` / `vaults.now`; `session_task.py` prints `Now:` before
   `main()` (a crash keeps the time); new `now.py` for UserPromptSubmit; `hooks.json` runs it, or
   `date` without python3. Check: `tests/test_now.py` runs the shipped hook commands with `TZ=UTC`
   against Asia/Tokyo, `$TZ` only, one `Now:` line, and the no-python3 fallback.
4. **Setup** — `set_timezone` action, `planner-setup timezone ZONE`, menu entry; `add-vault`
   keeps the field. Check: setup tests for write, create, unknown zone, dry run, add-vault, CLI.
5. **Text** — the planner Vault section's Date bullet, task-park, task-note and task-start take
   date and time from the latest `Now:` line; `docs/setup.md` gains a Timezone section.
6. **Release** — tasks 0.4.0, task-track 0.4.0, planner 0.5.1; rebuild `planner.plugin`; every
   suite in AGENTS.md; `claude plugin validate` for the three plugins.
