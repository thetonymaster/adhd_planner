#!/usr/bin/env bash
# Builds planner.plugin from planner-plugin/: validate, zip to a temp file, test the zip,
# check it holds exactly the source tree, then move it into place. A failed build leaves
# the previous planner.plugin and no temp files behind.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
src="$repo/plugins/planner"
out="$repo/planner.plugin"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

claude plugin validate "$src"
python3 -m unittest discover -s "$repo/tests"

(cd "$src" && find . -type f ! -name '.DS_Store' | sed 's|^\./||' | sort > "$work/tree.txt")
(cd "$src" && zip -q -X "$work/planner.plugin" -@ < "$work/tree.txt")
unzip -tq "$work/planner.plugin"
unzip -Z1 "$work/planner.plugin" | sort | diff -u "$work/tree.txt" - \
  || { echo "zip contents differ from $src" >&2; exit 1; }

mv "$work/planner.plugin" "$out"
echo "Built $out ($(wc -l < "$work/tree.txt" | tr -d ' ') files, version $(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$src/.claude-plugin/plugin.json"))"
