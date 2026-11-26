#!/usr/bin/env bash
# run_case.sh <out-dir> <case> <scenario> <turn1> [turn2]
# One headless case: fresh fixture vault, turn 1 with a preset session id, optional scripted reply via --resume.
# Writes <out-dir>/run-<case>/{vault,Tasks.before,Tasks.turn1,sid,turn1.txt,transcript.txt}; exits non-zero if a claude call fails.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$1"
out=$(cd "$1" && pwd); name=$2; sc=$3; t1=$4; t2=${5:-}
repo=$(cd "$here/../.." && pwd)
export STARTER=${STARTER:-$repo/examples/vault-starter}
PLUGIN=${PLUGIN:-$repo/plugins/tasks}
sid=$(uuidgen | tr "[:upper:]" "[:lower:]")
r=$("$here/make_vault.sh" "$out/run-$name" "$sc" "$sid")
echo "$sid" > "$r/sid"
cd "$r/work"
common=(--plugin-dir "$PLUGIN" --setting-sources project --strict-mcp-config
        --permission-mode acceptEdits --add-dir "$r/vault"
        --allowedTools "Read" "Write" "Edit" "Glob" "Grep" "Skill"
          "Bash(git rev-parse:*)" "Bash(mkdir:*)" "Bash(ls:*)" "Bash(cat:*)" "Bash(date:*)"
        --model sonnet --output-format text)
export ADHD_PLANNER_VAULTS=$r/vaults.json

# turn1.txt holds only the assistant's turn-1 output (what the "did it ask" checks read);
# transcript.txt is the human-readable log with the scripted prompts.
rc=0
claude -p "$t1" --session-id "$sid" "${common[@]}" </dev/null > "$r/turn1.txt" 2>&1 || rc=$?
{ echo "### turn 1: $t1"; cat "$r/turn1.txt"; } > "$r/transcript.txt"
# Undo turn 1's SessionEnd park (a live session does not end between question and answer),
# then snapshot: turn-2 effects are graded against this.
if [ -n "$t2" ]; then python3 "$here/session_end.py" "$r/vault/Tasks"; fi
cp -R "$r/vault/Tasks" "$r/Tasks.turn1"
if [ "$rc" -eq 0 ] && [ -n "$t2" ]; then
  { echo; echo "### turn 2: $t2"; } >> "$r/transcript.txt"
  claude -p "$t2" --resume "$sid" "${common[@]}" </dev/null >> "$r/transcript.txt" 2>&1 || rc=$?
fi
if [ "$rc" -ne 0 ]; then
  echo "EXIT $rc" >> "$r/transcript.txt"
  echo "case $name: claude exited $rc (see $r/transcript.txt)" >&2
  exit "$rc"
fi
echo "$r"
