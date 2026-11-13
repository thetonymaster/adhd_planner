#!/usr/bin/env bash
# Builds planner.plugin from plugins/planner/: validate, run tests/, zip to a temp file
# (minus EGM.md, caches and tools/out/), test the zip, check it holds exactly the source tree, read
# the version, then move it into place. A failed build leaves the previous planner.plugin
# and no temp files behind.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
src="$repo/plugins/planner"
out="$repo/planner.plugin"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

claude plugin validate "$src"
python3 -m unittest discover -s "$repo/tests"

(cd "$src" && find . -type f ! -name '.DS_Store' ! -name 'EGM.md' ! -path '*/__pycache__/*' ! -path './tools/out/*' ! -name '*.pyc' | sed 's|^\./||' | sort > "$work/tree.txt")
(cd "$src" && zip -q -X "$work/planner.plugin" -@ < "$work/tree.txt")
unzip -tq "$work/planner.plugin"
unzip -Z1 "$work/planner.plugin" | sort | diff -u "$work/tree.txt" - \
  || { echo "zip contents differ from $src" >&2; exit 1; }

# Read these before the mv: a failure inside echo's $(...) would not stop the script.
count=$(wc -l < "$work/tree.txt" | tr -d ' ')
version=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$src/.claude-plugin/plugin.json")

mv "$work/planner.plugin" "$out"
echo "Built $out ($count files, version $version)"
