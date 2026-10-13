#!/usr/bin/env bash
# SessionStart (startup|resume|clear|compact): inject time + active task's Next/Open loops.
VAULT="${VAULT:-$HOME/vault}"
NOTES="$VAULT/Tasks"
echo "Now: $(date '+%a %Y-%m-%d %H:%M')"
slug=$(tr -d '[:space:]' < "$NOTES/.active" 2>/dev/null)
[ -n "$slug" ] || { echo "No active task. Ask Q what we're working on, or suggest /task-start."; exit 0; }
f="$NOTES/$slug.md"
[ -f "$f" ] || { echo "Active task '$slug' has no note at $f."; exit 0; }
echo "Active task: $slug — full note: $f"
# Struck-through lines (~~done~~) stay in the note but not in every session's context.
awk '/^## (Goal|Next|Open loops)/{p=1;print;next} /^## /{p=0} p && !/^[[:space:]]*- (\[.\] )?~~/' "$f" | head -40
