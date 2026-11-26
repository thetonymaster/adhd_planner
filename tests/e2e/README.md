# tasks skills e2e

Drives real headless `claude -p` sessions through `/tasks:task-start` and `/tasks:task-switch` against throwaway vaults, then checks the vault state deterministically. Local only: it spends model calls (about 14 Sonnet turns) and is not part of CI or `unittest discover`.

```bash
bash tests/e2e/run.sh
```

- `make_vault.sh`: builds one fixture (starter vault, `vaults.json`, empty git repo, `Tasks.before/` snapshot) for a scenario: `session-owned`, `global`, `new`, `done`.
- `run_case.sh`: turn 1 with a preset `--session-id` (so the fixture can pre-write `Tasks/.session/<id>`), and an optional scripted reply via `--resume`. Loads only `plugins/tasks` (`--plugin-dir`, `--setting-sources project`).
- `check.py`: what each case must leave behind (`status:`, `.active`, `.session/<id>`, untouched notes). Only "did it ask" reads the transcript.

Known catch: every `claude -p` exit fires `SessionEnd`, and `park_on_end.py` parks the session's active task with a `parked: session ended` Log line (also between turn 1 and the reply). `check.py` counts that park as "active at session end" and ignores it when comparing notes. A failure that shows only that line is the harness, not the skill.

Add a case: a scenario in `make_vault.sh` if the fixture is new, a `case_` line in `run.sh`, an `EXPECT` entry in `check.py`.
