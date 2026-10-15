#!/usr/bin/env bash
# tasks plugin SessionStart hook: inject time + this session's vault, task and its Next/Open loops.
# session_task.py picks the vault and task (vaults.json, see vaults.py). Without python3: the single
# vault from the vaultPath option / $VAULT / ~/vault, and its Tasks/.active.
echo "Now: $(date '+%a %Y-%m-%d %H:%M')"
# The hook's JSON arrives on stdin; run by hand in a terminal there is none, so don't wait for it.
input=""
[ -t 0 ] || input=$(cat)
if command -v python3 >/dev/null; then
  HOOK_INPUT="$input" exec python3 "$(dirname "$0")/session_task.py"
fi
VAULT="${CLAUDE_PLUGIN_OPTION_VAULTPATH:-${VAULT:-$HOME/vault}}"
case "$VAULT" in "~") VAULT=$HOME ;; "~/"*) VAULT="$HOME/${VAULT#\~/}" ;; esac
NOTES="$VAULT/Tasks"
# No vault here (e.g. Cowork without the folder connected): the time is all there is to say.
[ -d "$NOTES" ] || exit 0
echo "Vault: $VAULT"
slug="$(tr -d '[:space:]' < "$NOTES/.active" 2>/dev/null)"
# Same rule as vaults.slug_or_empty: anything else could name a file outside Tasks/.
case "$slug" in ""|-*|*[!a-z0-9-]*) slug="" ;; esac
[ -n "$slug" ] || { echo "No active task. Ask the user what they're working on, or suggest /tasks:task-start."; exit 0; }
f="$NOTES/$slug.md"
[ -f "$f" ] || { echo "Active task '$slug' (global (python3 missing)) has no note at $f."; exit 0; }
echo "Active task: $slug (global (python3 missing)) — full note: $f"
awk '/^## (Goal|Next|Open loops)/{p=1;print;next} /^## /{p=0} p && !/^[[:space:]]*- (\[.\] )?~~/' "$f" | head -40
