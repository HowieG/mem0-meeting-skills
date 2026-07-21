#!/usr/bin/env bash
# Symlink this repo's skills into ~/.claude/skills/ so edits here take effect
# immediately and stay under version control.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.claude/skills"
VAULT="${MEM0_VAULT:-$HOME/Documents/mem0 vault}"

mkdir -p "$DEST"

for skill in "$REPO"/skills/*/; do
  name="$(basename "$skill")"
  target="$DEST/$name"

  if [ -L "$target" ]; then
    rm "$target"
  elif [ -e "$target" ]; then
    backup="$target.bak.$(date +%Y%m%d%H%M%S)"
    mv "$target" "$backup"
    echo "  ! $name existed as a real directory — moved to $backup"
  fi

  ln -s "${skill%/}" "$target"
  echo "  + $name -> $target"
done

echo
if [ -d "$VAULT" ]; then
  echo "  vault: $VAULT"
else
  echo "  ! vault not found at: $VAULT"
  echo "    clone the vault repo there, or export MEM0_VAULT=<path>"
fi

echo
echo "done. restart Claude Code to pick up the skills."
