#!/usr/bin/env bash
# tasks plugin SessionStart hook: inject time + this session's task Next/Open loops.
# Which task: Tasks/.session/<session_id> → the note whose `repo:` holds the session's cwd
# (deepest, then active, then newest; never `done`) → Tasks/.active.
VAULT="${CLAUDE_PLUGIN_OPTION_VAULTPATH:-${VAULT:-$HOME/vault}}"
case "$VAULT" in "~") VAULT=$HOME ;; "~/"*) VAULT="$HOME/${VAULT#\~/}" ;; esac
NOTES="$VAULT/Tasks"
echo "Now: $(date '+%a %Y-%m-%d %H:%M')"
# No vault here (e.g. Cowork without the folder connected): the time is all there is to say.
[ -d "$NOTES" ] || exit 0
# The skills read this line, so they edit the vault the vaultPath option chose.
echo "Vault: $VAULT"
# The hook's JSON arrives on stdin; run by hand in a terminal there is none, so don't wait for it.
input=""
[ -t 0 ] || input=$(cat)
picked=""
command -v python3 >/dev/null || picked="$(tr -d '[:space:]' < "$NOTES/.active" 2>/dev/null)"$'\t'"global (python3 missing)"
[ -n "$picked" ] || picked=$(HOOK_INPUT="$input" NOTES="$NOTES" python3 - <<'PY'
import json, os, pathlib, re, time

notes = pathlib.Path(os.environ["NOTES"])
home = os.path.expanduser("~")
try:
    data = json.loads(os.environ.get("HOOK_INPUT") or "{}")
except ValueError:
    data = {}
sid = str(data.get("session_id") or "")
cwd = str(data.get("cwd") or os.getcwd())

sessions = notes / ".session"
unpruned = []
if sessions.is_dir():
    cutoff = time.time() - 14 * 86400
    for f in sessions.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
        except FileNotFoundError:
            pass  # another session pruned it first
        except OSError as e:
            unpruned.append(f"{f.name} ({type(e).__name__})")

def norm(p):
    p = home + p[1:] if p == "~" or p.startswith("~/") else p
    return os.path.realpath(p)  # symlinked checkouts (e.g. iCloud) bind like their target

def field(block, name):
    m = re.search(rf'^{name}:\s*"?([^"\n]*?)"?\s*$', block, re.M)
    return m.group(1) if m else ""

def pick():
    slugs = {p.stem for p in notes.glob("*.md")} if notes.is_dir() else set()
    override = (sessions / sid).read_text().strip() if sid and (sessions / sid).is_file() else ""
    if override in slugs:
        return override, "this session"
    here = norm(cwd)
    bound = []
    for p in sorted(notes.glob("*.md")):
        try:
            text = p.read_text()
        except (OSError, UnicodeDecodeError):
            skipped.append(p.name)
            continue
        m = re.match(r"---\n(.*?)\n---", text, re.S)
        block = m.group(1) if m else ""
        repo, status = field(block, "repo"), field(block, "status")
        if not repo or status == "done":
            continue
        root = norm(repo)
        if here == root or here.startswith(root + "/"):
            bound.append((len(root), status == "active", p.stat().st_mtime, p.stem, repo))
    if bound:
        best = max(bound)
        return best[3], f"project: {os.path.basename(norm(best[4]))}"
    return global_slug(), "global"

def global_slug():
    active = notes / ".active"
    return active.read_text().strip() if active.is_file() else ""

skipped = []
try:
    slug, why = pick()
except Exception as e:
    # Never block session start: say what broke, then use the global task.
    slug, why = global_slug(), f"global (resolver error: {type(e).__name__}: {e})"
print(f"{slug}\t{why}")
if skipped:
    print(f"(skipped unreadable notes: {', '.join(skipped)})")
if unpruned:
    print(f"(could not prune .session/{', .session/'.join(unpruned)})")
PY
)
first=${picked%%$'\n'*}
rest=""
[ "$first" = "$picked" ] || rest=${picked#*$'\n'}
slug=${first%%$'\t'*}
why=${first#*$'\t'}
[ -n "$slug" ] || { echo "No active task. Ask Q what we're working on, or suggest /tasks:task-start."; exit 0; }
f="$NOTES/$slug.md"
[ -f "$f" ] || { echo "Active task '$slug' ($why) has no note at $f."; exit 0; }
echo "Active task: $slug ($why) — full note: $f"
[ -z "$rest" ] || echo "$rest"
# Struck-through lines (~~done~~) stay in the note but not in every session's context.
awk '/^## (Goal|Next|Open loops)/{p=1;print;next} /^## /{p=0} p && !/^[[:space:]]*- (\[.\] )?~~/' "$f" | head -40
