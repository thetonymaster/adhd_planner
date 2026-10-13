#!/usr/bin/env bash
# Installs Claude Code config into ~/.claude, the starter vault into $VAULT (default ~/vault),
# and merges settings.snippet.json into ~/.claude/settings.json. Anything it would change is
# backed up first under ~/.claude/backups/<timestamp>/ (outside skills/, so a backup is
# never loaded as a second copy of a skill). Re-running with nothing changed copies nothing.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
vault="${VAULT:-$HOME/vault}"
backups="$HOME/.claude/backups/$(date +%Y%m%d%H%M%S)"

# install <source> <installed path>: backs up the installed copy when it differs, then replaces it.
install() {
  local src=$1 dest=$2
  if [ -e "$dest" ]; then
    diff -rq "$src" "$dest" >/dev/null 2>&1 && return 0
    local rel=${dest#"$HOME/.claude/"}
    mkdir -p "$(dirname "$backups/$rel")"
    cp -R "$dest" "$backups/$rel"
    echo "Backup: $backups/$rel"
    rm -rf "$dest"
  fi
  mkdir -p "$(dirname "$dest")"
  cp -R "$src" "$dest"
  echo "Installed: $dest"
}

install "$here/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
install "$here/rules/composition.md" "$HOME/.claude/rules/composition.md"
# end-task.sh is retired (the task-track mod logs session ends); merge-settings.py unregisters it.
install "$here/hooks/load-task.sh" "$HOME/.claude/hooks/load-task.sh"
chmod +x "$HOME/.claude/hooks/load-task.sh"
for skill in "$here"/skills/*/; do
  install "${skill%/}" "$HOME/.claude/skills/$(basename "$skill")"
done

if [ -e "$vault" ]; then
  echo "$vault already exists — skipped vault copy"
else
  cp -R "$here/vault-starter" "$vault"
  mv "$vault/_claude" "$vault/.claude"
  echo "Vault created at $vault"
fi

python3 "$here/merge-settings.py"
