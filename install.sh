#!/usr/bin/env bash
# Set this machine up to read (and optionally run) the meeting pipeline.
#
#   ./install.sh            symlink skills, check the vault, report status
#   ./install.sh --clone    also clone the vault repo if it isn't there yet
#
# Re-runnable: existing symlinks are replaced, real directories are backed up
# rather than clobbered.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.claude/skills"
# Backups live OUTSIDE $DEST on purpose: anything inside it is loaded as a
# skill, so an in-place `foo.bak` becomes a duplicate ghost skill in the picker.
BACKUPS="$HOME/.claude/skill-backups"
VAULT="${MEM0_VAULT:-$HOME/Documents/mem0 vault}"
VAULT_REMOTE="git@github.com:HowieG/mem0-vault.git"
CLONE=false
[ "${1:-}" = "--clone" ] && CLONE=true

say() { printf '  %s\n' "$*"; }

echo
echo "mem0 meeting pipeline — install"
echo

# --- skills --------------------------------------------------------------
mkdir -p "$DEST"
for skill in "$REPO"/skills/*/; do
  name="$(basename "$skill")"
  target="$DEST/$name"

  if [ -L "$target" ]; then
    rm "$target"
  elif [ -e "$target" ]; then
    mkdir -p "$BACKUPS"
    backup="$BACKUPS/$name.$(date +%Y%m%d%H%M%S)"
    mv "$target" "$backup"
    say "! $name existed as a real directory — moved to $backup"
  fi

  ln -s "${skill%/}" "$target"
  say "+ $name"
done

# --- vault ---------------------------------------------------------------
echo
if [ ! -d "$VAULT" ]; then
  if $CLONE; then
    say "cloning vault -> $VAULT"
    git clone -q "$VAULT_REMOTE" "$VAULT"
    say "+ vault cloned"
  else
    say "! vault not found at: $VAULT"
    say "  run './install.sh --clone', or clone it yourself:"
    say "    git clone $VAULT_REMOTE \"$VAULT\""
    say "  if your vault lives elsewhere, export MEM0_VAULT=<path> and re-run"
    echo
    exit 1
  fi
elif [ ! -d "$VAULT/.git" ]; then
  say "! vault at $VAULT is not a git repo — updates won't pull"
else
  say "vault: $VAULT"
  say "  $(git -C "$VAULT" log --oneline -1 2>/dev/null || echo 'no commits yet')"
fi

# --- tooling -------------------------------------------------------------
echo
for tool in python3 git claude; do
  if command -v "$tool" >/dev/null 2>&1; then
    say "$tool: $(command -v "$tool")"
  else
    say "! $tool not on PATH — the pipeline needs it"
  fi
done

# --- verify --------------------------------------------------------------
echo
if MEM0_VAULT="$VAULT" python3 "$REPO/skills/granola-to-obsidian-howard/scripts/vaultmerge.py" >/dev/null 2>&1; then
  say "audit: clean"
else
  say "! audit reported problems — run it directly to see them:"
  say "  MEM0_VAULT=\"$VAULT\" python3 $REPO/skills/granola-to-obsidian-howard/scripts/vaultmerge.py"
fi

echo
echo "done. Open \"$VAULT\" in Obsidian, and restart Claude Code to load the skills."
echo
