#!/usr/bin/env bash
# Start / stop / inspect the unattended ingest loop.
#
#   ./bin/loop-control.sh start     load the launchd agent (ticks every 5 min)
#   ./bin/loop-control.sh stop      unload it — the demo pause switch
#   ./bin/loop-control.sh status    is it loaded? recent ledger lines
#   ./bin/loop-control.sh once      run a single tick right now, in the foreground
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.howieg.mem0.ingest"
PLIST_SRC="$REPO/launchd/$LABEL.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LEDGER="${MEM0_LEDGER:-$HOME/Library/Logs/mem0-meeting-ingest.log}"

case "${1:-status}" in
  start)
    mkdir -p "$HOME/Library/LaunchAgents"
    cp "$PLIST_SRC" "$PLIST_DEST"
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    launchctl load "$PLIST_DEST"
    echo "loop started — ticks every 5 minutes"
    ;;
  stop)
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    echo "loop stopped"
    ;;
  once)
    exec "$REPO/bin/ingest-tick.sh"
    ;;
  status)
    if launchctl list | grep -q "$LABEL"; then
      echo "loop: RUNNING"
    else
      echo "loop: stopped"
    fi
    echo
    echo "last 10 ledger lines ($LEDGER):"
    tail -10 "$LEDGER" 2>/dev/null || echo "  (no ticks yet)"
    ;;
  *)
    echo "usage: $0 {start|stop|once|status}" >&2
    exit 2
    ;;
esac
