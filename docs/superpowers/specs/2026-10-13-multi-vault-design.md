# Multiple vaults — design

Date: 2026-10-13 · Status: approved in chat, spec under review

## Goal

Register several Obsidian vaults (e.g. `personal`, `work`), each with its own `Tasks/`.
Every session resolves to exactly one vault (the *current vault*), which the `Vault:`
line, the skills, `vault-allow` and the task-track mod all use. Task lists and
`/task-switch` see tasks in every vault; switching to a task in another vault makes
that vault current for the session.

Today one path (`vaultPath` option → `$VAULT` → `~/vault`) is assumed by the `tasks`
hooks, the task-track mod, ~10 skills and `planner_setup`.

## Decisions (from the brainstorm)

| Question | Decision |
| --- | --- |
| Use case | Between "see all vaults at once" and "switch vault explicitly": registered vaults, one current per session, cross-vault list/switch. |
| Active task scope | **Per vault.** Each vault keeps its own `.active`, `.session/`, `.pomo.json`. Two sessions in two vaults can run two timers. |
| Where the vault list lives | One shared file, `~/.config/adhd-planner/vaults.json`. |
| Bind vaults to folders | Yes, optional `folders` per vault. |
| Implementation | Extend both resolvers in place (Python in `load-task.sh`, TS `resolve.ts`), kept in step by shared fixtures. The mod has `$.process.run`, but spawning Python on every `load()` plus an unverified stdout return makes an in-process resolver the safer choice. |

## 1. Config

Path: `$ADHD_PLANNER_VAULTS` if set, else `~/.config/adhd-planner/vaults.json`.

```json
{
  "default": "personal",
  "vaults": {
    "personal": { "path": "~/vault" },
    "work":     { "path": "~/work-vault", "folders": ["~/work"] }
  }
}
```

- Vault names are kebab-case (`^[a-z0-9][a-z0-9-]*$`). They are the prefix in
  `work:deploy-fix` and the label in lists, the status line and the `Vault name:` line.
- `path` is required. `folders` is optional; entries are `~`-expanded and
  symlink-resolved, the same normalization `repo:` gets today.
- `default` is required when there are 2+ vaults; with one vault it defaults to that one.

**No file:** behave exactly as today. One implicit vault named `default` at
`CLAUDE_PLUGIN_OPTION_VAULTPATH` → `$VAULT` → `~/vault`. The `vaultPath` options stay.

**Invalid file** (unparseable JSON, a vault without `path`, a bad name, `default` not in
`vaults`, 2+ vaults without `default`, the same folder listed by two vaults):

- SessionStart prints `Vault config error: <file>: <what is wrong, with the value>; using <fallback path>`
  and continues with the implicit vault. It never blocks session start.
- The mod shows the same text in its `problem` slot and uses the implicit vault.
- `vault-allow` uses only the implicit vault.

**A vault whose `path` has no `Tasks/`** is skipped (e.g. iCloud not mounted). SessionStart
names it once: `(skipped vault work: no Tasks/ at <path>)`. Not an error. If the default
vault is skipped and nothing else matches, output is today's "no vault" output.

Out of scope: per-vault Obsidian CLI config, per-vault templates (each vault has its own
`Templates/`), setup UI beyond one "add vault" step.

## 2. Resolution: which vault and task a session shows

Inputs: the parsed config, the session id, the session's `cwd`, and each usable vault's
notes and pointer files. First match wins:

1. **Session override.** Any vault whose `Tasks/.session/<sid>` holds a slug whose note
   exists. If several vaults have one, the newest file mtime wins. → that vault, that slug.
   Reason: `this session`.
2. **Repo match.** Across all vaults, non-`done` notes whose `repo:` holds `cwd`. Deepest
   repo wins, then `status: active`, then newest note mtime (today's tiebreak, now across
   vaults). → that note's vault and slug. Reason: `project: <repo basename>`.
3. **Folder binding.** The deepest `folders` entry, over all vaults, that holds `cwd`.
   → that vault, its `Tasks/.active`. Reason: `folder <entry as written>`.
4. **Default.** → the `default` vault, its `Tasks/.active`. Reason: `default`
   (`global` when no config file exists, as today).

A repo note beats a folder binding even when the binding is in another vault and covers
the cwd: a note's `repo:` is the more specific statement.

Within the chosen vault, the per-vault state is unchanged: `.active`, `.session/`,
`.pomo.json`, and the 14-day `.session/` prune (now run in every usable vault).

### SessionStart output

`Vault: <path>` stays byte-identical because skills parse it. When a config file exists,
one line follows it:

```
Vault: /Users/you/work-vault
Vault name: work (folder ~/work) · others: personal
Active task: deploy-fix (project: sre-iac) — full note: /Users/you/work-vault/Tasks/deploy-fix.md
```

`others:` lists the other usable vault names. With no config file the output is
unchanged from today.

### Mod (task-track)

`pickTask` grows the same four steps over the same inputs. The status line and pane get
a `<vault> · ` prefix only when 2+ vaults are registered; single-vault output is
unchanged. The pomodoro reads and writes the current vault's `Tasks/.pomo.json`. If the
current vault changes mid-session (cross-vault `/task-switch`), focus credit is flushed
to the previous task's note, the same as a task change today.

## 3. Skills, permissions, setup

**`vault-allow.py`** approves a file tool when every path is inside one registered usable
vault, and adds that vault (not all vaults) via `addDirectories`. A Glob or Grep whose
paths span two vaults gets no output (normal prompt).

**Task skills.** `<slug>` means the current vault; `<vault>:<slug>` names another one.

- `task-switch` with no argument lists `active`/`parked` tasks from all usable vaults,
  max 5 overall, newest first, each as `<vault>:<slug>` (bare slug when one vault).
- `task-switch work:x` from another vault: write `x` to `work/Tasks/.session/<sid>` and
  `work/Tasks/.active`, delete `<old vault>/Tasks/.session/<sid>`, and reply with
  `Vault now: work (<path>)`. The rest of the session uses that vault.
- `task-start [<vault>:]<slug>` creates the note in the current vault, or the named one;
  the reply names the vault when 2+ are registered.
- `task-park` parks the current vault's active task (unchanged otherwise).
- `task-note` (Cowork has no hook) finds the vault as: the `Vault:` line → `vaults.json`
  default → today's lookup chain. "Which tasks are open" covers all usable vaults.

**`obsidian-vault` and planner skills** (break-down-task, eod-shutdown, morning-startup,
plan-day, plan-week, capture-triage, setup): "find it once" becomes the `Vault:` line →
`vaults.json` default → today's chain. They read and write only the current vault; inbox
triage stays per vault. No cross-vault features.

**`planner_setup`** gets one optional step, "add another vault": name, path, folders →
create or merge `vaults.json` (existing entries kept; first vault becomes `default` if
none). A run with only `~/vault` writes no file.

**Docs:** a "Multiple vaults" section in `docs/setup.md` and in the `tasks` and
`task-track` READMEs.

## 4. Testing

Baseline on `main` @ 0affff0: `tests/` 35 OK · `setup` 40 passed · `task-track` 98 pass.
Existing tests stay unmodified as the no-config regression guard.

- **Shared fixtures** `tests/fixtures/vault-resolution.json`: each case is
  `{config, notes per vault, .active/.session files with mtimes, cwd, sid}` →
  `{vault, slug, reason}`. `test_load_task.py` runs the hook over every case;
  `task-track.test.ts` runs `pickTask` over the same file. Divergence fails a test.
- **Cases:** each of the 4 steps alone; repo note beats folder binding in another vault;
  deepest folder wins; session override in 2 vaults → newest; no config → today's
  output; unparseable JSON, unknown `default`, duplicate folder → error line + fallback;
  vault without `Tasks/` → skipped line; `~` paths. Symlinked paths are a Python-only
  case: the mod's `normalize()` does not resolve symlinks today (no realpath in its API),
  so that case stays out of the shared fixtures.
- **`test_vault_allow.py`:** path in 2nd vault → allow with that vault in
  `addDirectories`; Glob spanning both → no output; no config → today.
- **Mod:** two vaults with independent `.pomo.json`; `<vault> · ` prefix only with 2+;
  cross-vault switch flushes focus to the previous note.
- **Setup:** add-vault merges without dropping entries; single-vault run writes nothing.
- **Skills** (prose): manual smoke test in the plan — `/task-switch work:x` across
  vaults, then a new session in a bound folder shows the `work` task.
