#!/usr/bin/env bash
# run_case.sh <out-dir> <case> <scenario> <turn1> [turn2]
# One headless case: fresh fixture vault, turn 1 with a preset session id, optional scripted reply via --resume.
# Writes <out-dir>/run-<case>/{vault,Tasks.before,sid,transcript.txt}.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
out=$1; name=$2; sc=$3; t1=$4; t2=${5:-}
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
{
  echo "### turn 1: $t1"
  claude -p "$t1" --session-id "$sid" "${common[@]}" </dev/null 2>&1 || echo "EXIT $?"
  if [ -n "$t2" ]; then
    echo; echo "### turn 2: $t2"
    claude -p "$t2" --resume "$sid" "${common[@]}" </dev/null 2>&1 || echo "EXIT $?"
  fi
} > "$r/transcript.txt"
echo "$r"
