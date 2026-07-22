#!/usr/bin/env bash
# One tick of the unattended pipeline: fetch new Circleback meetings, ingest
# them into the vault, push if anything changed.
#
# Run by launchd every 5 minutes. Safe to run by hand. Idempotent: a tick with
# no new meetings writes nothing to the vault and makes no commit.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$REPO/skills/meeting-ingest/scripts"
VAULT="${MEM0_VAULT:-$HOME/Documents/mem0 vault}"
SOURCE_DIR="${MEM0_TRANSCRIPTS:-$HOME/Desktop/resources/circleback-inbox}"
WINDOW_DAYS="${INGEST_WINDOW_DAYS:-7}"
LEDGER="${MEM0_LEDGER:-$HOME/Library/Logs/mem0-meeting-ingest.log}"

mkdir -p "$(dirname "$LEDGER")"
stamp() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "$(stamp) $*" >> "$LEDGER"; }

# --- single-instance lock -------------------------------------------------
# Extraction takes minutes; the loop fires every 5. Overlap is the normal case,
# not an edge case. Two ticks writing the same notes and both running `git
# commit` is precisely the concurrency hazard v1 is meant to avoid — and unlike
# launchd (which refuses to start a second instance of a job under one label),
# a cron/`/loop` trigger will happily start one. mkdir is atomic on every FS
# that matters, so it is the lock.
LOCK="${MEM0_LOCK:-${TMPDIR:-/tmp}/mem0-ingest-tick.lock}"
if ! mkdir "$LOCK" 2>/dev/null; then
  HELD_BY="$(cat "$LOCK/pid" 2>/dev/null || echo unknown)"
  if [ "$HELD_BY" != unknown ] && ! kill -0 "$HELD_BY" 2>/dev/null; then
    # Previous run died without releasing. Reclaim rather than wedge forever.
    log "lock: stale (pid $HELD_BY gone) — reclaiming"
    rm -rf "$LOCK"
    mkdir "$LOCK" 2>/dev/null || { log "lock: could not reclaim, skipping tick"; exit 0; }
  else
    log "skipped: previous tick still running (pid $HELD_BY)"
    exit 0
  fi
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

# A tick must never leave the loop wedged: if any stage fails, log it and let
# the next tick retry. The vault is the only state, so a failed tick is a
# no-op, not a corruption.

# --- Stage 1: fetch ------------------------------------------------------
# MCP tool calls can only be made by an agent, so fetching is a headless
# Claude run. It writes normalized transcripts to SOURCE_DIR and nothing else.
#
# MEM0_SKIP_FETCH=1 ingests whatever is already in SOURCE_DIR without calling
# Circleback — for rehearsing the loop, and for backfilling transcripts that
# were dropped in by hand.
if [ "${MEM0_SKIP_FETCH:-0}" = "1" ]; then
  log "fetch: skipped (MEM0_SKIP_FETCH=1)"
else
FETCH_PROMPT="Fetch new Circleback meetings and save them as transcript files.

1. Call SearchMeetings with pageIndex 0 and a startDate of ${WINDOW_DAYS} days
   before today, endDate today.
2. For each meeting returned, check whether any file under \"$VAULT/Meetings\"
   already contains its id. Skip those — they are already ingested.
3. For meetings that remain, call GetTranscriptsForMeetings (batch them, up to
   50 ids per call).
4. For each returned transcript, write it to disk using the project's
   normalizer — do not hand-roll the format:

   import sys; sys.path.insert(0, '$SCRIPTS')
   from circleback_fetch import write_transcript
   write_transcript(meeting_dict, transcript_list, '$SOURCE_DIR')

   where meeting_dict has id/name/createdAt from SearchMeetings and
   transcript_list is the segment list from GetTranscriptsForMeetings.
   A meeting whose transcript is empty is still processing — write_transcript
   returns None for it, which is correct. Do not write a partial file.
5. Print one line: FETCHED <n> where n is the number of files written.

Do not modify the vault. Do not ingest. Fetching is the whole job."

FETCH_OUT="$(MEM0_FETCH_TIMEOUT=${MEM0_FETCH_TIMEOUT:-600} \
  timeout "${MEM0_FETCH_TIMEOUT:-600}" claude -p "$FETCH_PROMPT" \
  --add-dir "$SOURCE_DIR" \
  --allowedTools "Read" "Write" "Glob" "Grep" "Bash(python3:*)" \
  "mcp__circleback__SearchMeetings" "mcp__circleback__GetTranscriptsForMeetings" \
  2>&1)"
FETCH_RC=$?
if [ $FETCH_RC -ne 0 ]; then
  log "fetch FAILED (exit $FETCH_RC) — retrying next tick"
  exit 0
fi
log "fetch: $(echo "$FETCH_OUT" | grep -o 'FETCHED [0-9]*' | tail -1 || echo 'no count reported')"
fi

# --- Stage 2: ingest -----------------------------------------------------
python3 "$SCRIPTS/batch.py" "$SOURCE_DIR" --window-days "$WINDOW_DAYS"
INGEST_RC=$?
if [ $INGEST_RC -ne 0 ]; then
  log "ingest FAILED (exit $INGEST_RC) — vault left unchanged, retrying next tick"
  exit 0
fi

# --- Stage 3: publish ----------------------------------------------------
# Only commits when the vault actually changed, so quiet ticks leave no trace
# in git history. This is what makes "no new meetings" observable as silence.
cd "$VAULT" || { log "publish: vault not found at $VAULT"; exit 0; }

# Capture status and exit code separately. `[ -z "$(git status)" ]` treats any
# git failure -- not a repo, index.lock held by Obsidian -- as "no changes", so
# publishing would silently never happen while the ledger reported health.
CHANGES="$(git status --porcelain 2>/dev/null)"
GIT_RC=$?
if [ $GIT_RC -ne 0 ]; then
  log "publish: git status FAILED (exit $GIT_RC) in $VAULT — not published"
  exit 0
fi
if [ -z "$CHANGES" ]; then
  log "publish: vault unchanged, no commit"
  exit 0
fi

git add -A
git commit -qm "chore(vault): automated ingest $(stamp)" || { log "publish: commit failed"; exit 0; }
if git push -q 2>/dev/null; then
  log "publish: pushed $(git rev-parse --short HEAD)"
else
  log "publish: committed $(git rev-parse --short HEAD) but push failed — will push next tick"
fi
