#!/usr/bin/env bash
# run.sh [out-dir] — run every task-start/task-switch e2e case in parallel, then grade them.
# Spends real model calls (2 `claude -p` per two-turn case, Sonnet). Local only, not in CI.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
out=${1:-$(mktemp -d "${TMPDIR:-/tmp}/planner-e2e.XXXXXX")}
mkdir -p "$out"

pids=()
case_() { "$here/run_case.sh" "$out" "$@" >/dev/null & pids+=($!); }
case_ s-yes    session-owned "/tasks:task-start fix-bug" "yes"
case_ s-no     session-owned "/tasks:task-start fix-bug" "no"
case_ g-leave  global        "/tasks:task-start fix-bug" "Leave it as is"
case_ g-park   global        "/tasks:task-start fix-bug" "Park it"
case_ new      new           "/tasks:task-start new-thing" "Goal: prove e2e works. Project: ADHD Planner. First action: write the harness."
case_ done     done          "/tasks:task-start fix-bug"
case_ sw-done  done          "/tasks:task-switch fix-bug"
case_ sw-leave global        "/tasks:task-switch fix-bug" "Leave it as is"
failed=0
for p in "${pids[@]}"; do wait "$p" || failed=$((failed + 1)); done

echo "Runs: $out (transcript.txt per case)"
python3 "$here/check.py" "$out"
if [ "$failed" -ne 0 ]; then echo "$failed case(s) had a failed claude call" >&2; exit 1; fi
