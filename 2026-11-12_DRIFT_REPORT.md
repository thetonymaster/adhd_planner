# EGM Drift Report — 2026-11-12

> **Superseded.** This report was taken on `feat/task-list-skill` (4b84779), before PRs #8 and #9
> reached `main`. Branch `fix/egm-drift` re-synced all 13 contracts to `main` (e7ca450), re-ran
> drift detection there (14 candidates, 12 confirmed by 3 skeptics each) and fixed the confirmed
> items. Kept as the record of the first pass; line numbers below refer to 4b84779.

Scope: the 13 `EGM.md` contracts written by the EGM bootstrap on 2026-11-12, checked against the
code on branch `feat/task-list-skill` by three read-only reviewers that had not seen the
bootstrap conversation. Findings marked ✔ were re-checked by hand against the source.

## Triage — code-side findings (the code, not the contract, is wrong or risky)

1. ✔ **`planner.plugin` would ship the contracts.** `scripts/build-plugin.sh:15` zips every file
   under `plugins/planner`, so `plugins/planner/EGM.md` and `plugins/planner/tools/EGM.md` land in
   the Cowork upload on the next build (today's `planner.plugin` has none). Decide: exclude
   `EGM.md` in the `find`, or accept it and bump the version.
2. ✔ **Vault resolution is not identical across Python and TypeScript.** `vaults.py` resolves
   symlinks (`norm` → `realpath`, vaults.py:49-51); `resolve.ts` does not (resolve.ts:154, accepted
   in a code comment, "see spec §4"). A symlinked repo or folder can resolve to different tasks in
   the hook vs the mod. Only the Python side tests it (tests/test_load_task.py:149).
3. ✔ **`vault-allow.py` can exit 1.** A `file_path` with a NUL byte raises `ValueError` from
   `realpath`; `main` catches only `AttributeError`/`TypeError` (vault-allow.py:190). Fails toward
   the normal prompt (no allow), so not a security hole, but breaks the "always exits 0" rule.
4. ✔ **`build-plugin.sh` can fail after replacing `planner.plugin`.** The version is read after
   the `mv` (build-plugin.sh:21-22).
5. **Focus can be double-logged.** `flushFocus` reads, writes notes, then marks logged with no
   compare-and-set (register.tsx:483-492, :460). Two sessions flushing together can write the same
   focus line.

Smaller code-side items: `plan_day.py`/`plan_week.py` `--work`/`--lunch` flags skip
`planner_config` validation (traceback, exit 1; reversed ranges accepted); `docs/setup.md:32`
omits `add-vault --existing-name`; `docs/setup.md:35` overclaims backups; Cowork steps printed by
`actions.cowork` differ from `docs/setup.md:89`; `actions.py:1` docstring says "seven" actions
(there are eight); `build-plugin.sh:2` header says `planner-plugin/`; `types/index.d.ts:42`
comment says tool calls don't count as activity (they do); `task-list` / `task-note` skills use
a vault order that skips the `vaultPath` option.

---

## EGM.md

- System Verification omits the planner-dev suite (`cd .claude/skills/planner-dev && claude plugin test .`), CI's marketplace `claude plugin validate .` and `uv build`; CI runs `uv run --locked pytest` (ci.yml:28-39).
- The resolution order is restated in more skills than named: also `task-note`, `task-list`, and planner skills (e.g. eod-shutdown/SKILL.md:93-100, break-down-task/SKILL.md:80-87).
- The vaultPath → `$VAULT` → `~/vault` step lives in `actions.py:57-66` (`_current_vault`), not `paths.py`/`settings.py`.
- Marketplace name is also hard-coded in `setup/src/planner_setup/paths.py:12`.
- ✔ `~/.claude/CLAUDE.md` is not backed up: `claude_md` writes only when absent, via `shutil.copy2` (actions.py:236-246).
- Omits that `planner-setup` creates a vault (`copytree` of `examples/vault-starter`, actions.py:153).

## plugins/EGM.md

- "Slugs match the regex everywhere": `pickTask` returns slugs without `isSlug` checks (resolve.ts:33-56); test-only, and production goes through `taskNotePath`, which throws (resolve.ts:74-76).
- `vault-cases.ts` is consumed by `tests/test_load_task.py:221` and the TS tests, not `tests/test_vaults.py`.
- Planner-folder side effects omit `inbox-archive.md` (triage.py:147-152) and `habits-log.json` (habits.py:22, 39-41).

## plugins/planner/EGM.md

- morning-startup runs `triage.py`, `plan_day.py` and `make_daily.py` itself (morning-startup/SKILL.md:49-51, 68, 77), not "chains plan-day and daily-page".
- schedule-workflow runs `triage.py parse`/`apply` (schedule-workflow/SKILL.md:102-108).
- setup also runs `make_insert.py`, `triage.py`, `habits.py`, `plan_day.py`, `make_daily.py` and writes `tools/out/_setup_tasks.json` (setup/SKILL.md:131-136).
- "Seeding never overwrites user data" is a skill instruction (setup/SKILL.md:83-86), not code; the same step overwrites older tool scripts (:76-81).
- ✔ Does not acknowledge that `build-plugin.sh` packages these `EGM.md` files (see Triage 1).

## plugins/planner/tools/EGM.md

- ✔ `plan_week.py` deletes stale `week-tasks-<date>.json` on re-run (plan_week.py:221-224); not in Side Effects.
- "Exit 2 on `ConfigError`" covers `calendars.json` only; CLI `--work`/`--lunch` use each script's own `parse_range` (plan_day.py:51-53, plan_week.py:48-50): malformed → traceback exit 1, reversed ranges accepted.
- `habits.py log`: the day is rebuilt from current `habits.json` (habits.py:73), so marks for removed ids are dropped; unknown ids exit 0 (:66-69); `save_log` is not atomic (:39-41); `--done` is optional (:164).
- `triage.py apply` also drops blank lines, empty `- ` placeholders and template lines, and rewrites from `INBOX_TEMPLATE` (triage.py:48, 60, 153).
- `calendars.json` description omits `type_defaults`, which `add_event.py:51` requires.
- `add_event.py` reads `calendars.json` with raw `json.load` (add_event.py:38-40), bypassing `ConfigError`; exits 1 on a bad spec (:138-140).
- "Used by skill" column omits morning-startup, schedule-workflow and setup callers.
- "Seeding is additive" is skill prose (setup/SKILL.md:83-86), not enforced in `tools/`.

## plugins/tasks/EGM.md

- Only `task-switch` restates the hook's task pick order (task-switch/SKILL.md:16); `task-park` uses its own order (:8); `task-start` and `obsidian-vault` restate only the vault fallback.
- `task-list` and `task-note` carry a different vault order (skip `vaultPath`, add a folder named `vault`) (task-list/SKILL.md:16-21, task-note/SKILL.md:17-22): skill drift or missing from the contract.
- Side effects omit: task-start writes the daily note (task-start/SKILL.md:17); task-start/task-switch delete the other vault's `.session/<id>` (task-start:11, task-switch:14); task-switch writes `status:`/`repo:` frontmatter (:14-15).

## plugins/tasks/hooks/EGM.md

- Allow JSON includes `"hookEventName": "PermissionRequest"` (vault-allow.py:202-205).
- Interface omits `inside`, `hidden_note_in`, `parts_under`, `hidden`, `paths_of` and module constants (vault-allow.py:31-160).
- Output shape omits config error/warning, skipped-vault, `· others:`, no-active-task, missing-note and prune lines (session_task.py:72-110); `STRUCK` drops only `- ~~` / `- [x] ~~` list items (:16).
- ✔ "Always exits 0" is false for NUL paths (see Triage 3).
- Grep allows any single regular file without a dot-segment, not only notes (vault-allow.py:137).
- Root guard also refuses ancestors of `~/.claude`/`$CLAUDE_CONFIG_DIR` (:46) and returns no roots if any vault path is relative (:62-63).
- Omits the Glob pattern rule (`pattern_escapes`: absolute, `~`, `{`, dot-segment; :77-81, :188).
- Prune failures are reported only when the picked note exists (session_task.py:94-110).
- "All three hooks read vaults.json, frontmatter, `.active`, `.session`" is false: `now.py` reads only vaults.json; `vault-allow.py` no frontmatter/state; the bash fallback no vaults.json.
- ✔ "Same resolution as resolve.ts": not for symlinks (see Triage 2).

## plugins/task-track/EGM.md

- Tests also include `tests/fixtures/vault-case.ts` (the `VaultCase` type).
- ✔ Sync claim with `vaults.py` already broken for symlinks (see Triage 2).
- Side effects omit: leftover `Tasks/.pomo.json.<id>.tmp` when `mv` fails (register.tsx:267-280); pane notes appended as a user message via `$.session.append` (:555-557); reads `Templates/Daily.md` (:313-315).

## plugins/task-track/hooks/EGM.md

- ✔ "Mirrors vaults.py": not for symlinks (see Triage 2).
- `pickTask` is test-only (register.tsx:29 imports only `pickVault`) and skips `isSlug`.
- ✔ Tool calls do set `lastActiveAt`: `tool.call` → `markActive($, true)` (register.tsx:646) → `touch` (pomo.ts:212-213).
- "At most once a minute": `shouldTouch` also writes on task change or when a block can start (pomo.ts:192-196).
- The announcer is the session whose write survives read-back (register.tsx:506-511), i.e. the last writer.
- "Focus credited once" is not enforced for note writes (see Triage 5).
- Temp file name uses `SESSION`, which is per module load (register.tsx:51-52).
- The pane note field uses `$.session.append`, not hidden context (register.tsx:555-557).
- With 2+ vaults, the store key falls back to `focus:YYYY-MM-DD` when no config entry matches (register.tsx:296-297); keys are written only on day rollover (:374-377).

## plugins/task-track/types/EGM.md

No drift detected.

## scripts/EGM.md

- ✔ Not fully atomic: the version read after `mv` can fail (build-plugin.sh:21-22).
- Required tools also include `wc`, `tr`, `dirname`, `mv`, `rm`.
- Unverified: "`planner.plugin` shows modified after every run" — `zip -X` may be byte-identical with unchanged mtimes.

## setup/EGM.md

- "Never commit copies inside `src/planner_setup/examples`" is convention only; `setup/.gitignore` does not ignore it.
- ✔ `docs/setup.md:32` omits `add-vault --existing-name` (cli.py:38).
- `docs/setup.md:35` says anything changed is backed up; only `settings.json`/`vaults.json` are (files.py:57), and folders may carry `-n`.
- Cowork steps printed by code (actions.py:253-256) differ from `docs/setup.md:89`.
- `docs/setup.md:124`: seeding happens whenever `vaults.json` lacks a `vaults` key, not only when absent (actions.py:221).

## setup/src/EGM.md

No drift detected.

## setup/src/planner_setup/EGM.md

- ✔ `status` returns 0 when `claude` is missing or `_state` fails (actions.py:75-78, 94); only `install` returns 1.
- `SystemExit(<str>)` exits (files.py:19, 21; settings.py:27; paths.py:48) are exit 1 to stderr, not in the exit-code list; `paths.examples()` raising is undocumented.
- ✔ Change lines do print the value for `permissions.allow` (settings.py:68); only the vault path is hidden.
- `permissions.additionalDirectories: add vault` cannot come from `configure`; `desired()` never sets it (settings.py:14-20).
- `install --dry-run` prints lowercase `would run: claude ...` (actions.py:113).
- Code-side: `actions.py:1` docstring says "seven" actions; there are eight.
