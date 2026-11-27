#!/usr/bin/env bash
# make_vault.sh <root> <scenario> <session-id>
# Builds an isolated vault + vaults.json + git repo for one start/switch scenario.
set -euo pipefail
root=$1; scenario=$2; sid=$3
: "${STARTER:?set STARTER to examples/vault-starter}"

rm -rf "$root"; mkdir -p "$root"
vault=$root/vault; work=$root/work
cp -R "$STARTER" "$vault"
rm -f "$vault/Tasks/"*.md "$vault/Tasks/.active"
mkdir -p "$vault/Tasks/.session" "$work"
git -C "$work" init -q
printf '{"default":"e2e","vaults":{"e2e":{"path":"%s"}}}\n' "$vault" > "$root/vaults.json"

note() { # slug status [repo]
  cat > "$vault/Tasks/$1.md" <<EOF
---
status: $2
up: "[[ADHD Planner]]"
priority: p3
due:
repo: ${3:-}
started: 2026-11-20
finished:
aliases: []
tags: [task]
---
# $1

## Goal
E2E fixture task $1.

## Next
- [ ] first step of $1 (~15 min)

## Open loops

## Parked

## Log
- [[2026-11-20]] 09:00 — created
EOF
}

case $scenario in
  session-owned)   # this session is on old-work; fix-bug is backlog
    note old-work active; note fix-bug parked
    echo old-work > "$vault/Tasks/.session/$sid"; echo old-work > "$vault/Tasks/.active" ;;
  global)          # old-work is current only via .active; fix-bug is backlog
    note old-work active; note fix-bug parked
    echo old-work > "$vault/Tasks/.active" ;;
  new)             # no current task, fix-bug does not exist
    : ;;
  done)            # fix-bug is finished
    note fix-bug done ;;
  *) echo "unknown scenario: $scenario" >&2; exit 2 ;;
esac
# snapshot for "untouched" assertions
cp -R "$vault/Tasks" "$root/Tasks.before"
echo "$root"
