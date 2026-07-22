---
name: meeting-ingest
version: 0.1.0
description: Ingest normalized Circleback meeting transcripts into the Obsidian vault without human input. Use to ingest a transcript file, validate a Circleback export, or run the unattended pipeline step. Triggers on "ingest this transcript", "run meeting ingest".
---

# Meeting Ingest

Source-agnostic ingest driver. v1 speaks one format: normalized Circleback
exports (`meeting_id` header, `[MM:SS] **Name:** text` segments under
`## Transcript`). The parser refuses anything else — loudly, because an empty
parse downstream is indistinguishable from "no new meetings".

## Ingest one file

```bash
python3 <this-dir>/scripts/ingest.py <transcript.md>
```

- Parses fail-loud, skips if a Meetings/ note already carries the
  `meeting_id`, otherwise runs the semantic extractor headlessly
  (`claude -p`) under the pipeline skill's rules with non-interactive
  overrides, then audits.
- Exit 0 ⇔ meeting is in the vault and the audit is clean.
- Never blocks on a human: unresolved identities are written
  `status: unconfirmed` with `Unknown` fields — `/brain-resolution` clears
  them later.

## Unattended tick (what `/loop` runs)

One tick = fetch new meetings from Circleback, ingest them, publish the vault.

Start it with:

```
/loop 5m Run one meeting-ingest tick: follow the "Unattended tick" section of the meeting-ingest skill exactly.
```

**You are exactly two steps. Do these and nothing else.**

**Always run step 1, even if a previous ingest is still going.** Extraction
takes minutes and ticks fire every 5, so step 2 will often find the lock held
and skip — but fetching writes only to the inbox, never the vault, and
id-suffixed filenames cannot collide. A tick that skips step 1 because it
expects step 2 to be blocked wastes the window entirely; a tick that fetches
anyway leaves the next one with work already staged and no fetch latency.
Keep the inbox running ahead of the ingester.

### Step 1 — Fetch (only you can do this; MCP needs an agent)

```
REPO=/Users/howardgil/Desktop/resources/mem0-meeting-skills
INBOX=/Users/howardgil/Desktop/resources/circleback-inbox
```

1. `SearchMeetings` with `pageIndex: 0`, `startDate` = 7 days before today,
   `endDate` = today.

   **How many to fetch.** Keep **2–3 unprocessed transcripts staged** in the
   inbox at all times. Fetch enough to top up to that depth, not the entire
   backlog: the ingester consumes roughly one per tick, so a small buffer
   absorbs lock-blocked ticks without pulling hundreds of transcripts through
   your context. If the inbox already holds 3 un-ingested files, fetch nothing
   and go straight to step 2.

   **Backlog fallback.** If that returns nothing — or everything it returns is
   already in the vault — search again over the last 120 days and top the
   buffer up from the **most recent meetings not yet ingested**, newest first.
   To see what is already ingested:

   ```bash
   python3 -c "
   import pathlib, re, os
   v = pathlib.Path(os.environ.get('MEM0_VAULT', pathlib.Path.home()/'Documents'/'mem0 vault'))
   for n in sorted((v/'Meetings').glob('*.md')):
       m = re.search(r'^meeting-id:\s*\"?([^\"\n]+?)\"?\s*$', n.read_text(), re.M)
       if m: print(m.group(1))"
   ```

   A meeting fetched via the fallback is dated in the past, so pass a wide
   `--window-days` to step 2 or `find_candidates` will filter it straight back
   out. Real meetings from the live window need no such flag.

2. `GetTranscriptsForMeetings` for the ids you settled on (batch, ≤50 per call).
3. Write each transcript with the project's normalizer. **Never hand-roll the
   format** — the parser rejects anything else, deliberately:

   ```bash
   python3 -c "
   import sys, json; sys.path.insert(0, '$REPO/skills/meeting-ingest/scripts')
   from circleback_fetch import write_transcript
   m, t = json.loads(sys.argv[1]), json.loads(sys.argv[2])
   print(write_transcript(m, t, '$INBOX'))" \
     '{\"id\":\"...\",\"name\":\"...\",\"createdAt\":\"2026-07-21T10:00:00.000Z\"}' \
     '[{\"speaker\":\"...\",\"text\":\"...\",\"timestamp\":5.2}]'
   ```

   `m` needs `id`, `name`, `createdAt` from `SearchMeetings`; `t` is the segment
   list from `GetTranscriptsForMeetings`.

   An empty transcript means Circleback is still processing — `write_transcript`
   returns `None` and writes nothing. That is correct: a partial file would let
   the id filter mark the meeting done forever.

### Step 2 — Ingest and publish (one command, no improvising)

```bash
MEM0_SKIP_FETCH=1 /Users/howardgil/Desktop/resources/mem0-meeting-skills/bin/ingest-tick.sh
```

If you fetched a backlog meeting (older than the live window), widen the window
for this run so it isn't filtered back out:

```bash
MEM0_SKIP_FETCH=1 INGEST_WINDOW_DAYS=120 \
  /Users/howardgil/Desktop/resources/mem0-meeting-skills/bin/ingest-tick.sh
```

This skips only the fetch you just did, then: filters out meetings already in
the vault, runs an isolated headless extraction per new meeting (so a long
transcript never floods your context), audits, and commits + pushes the vault
**only if it changed**.

### Then report one line

Meetings fetched, ingested, skipped, and whether it pushed. Read the result from
the ledger:

```bash
tail -3 ~/Library/Logs/mem0-meeting-ingest.log
```

**Never ask the user anything during a tick**, and never hand-edit the vault to
"help" — gaps are written as `status: unconfirmed` and cleared later by
`brain-resolution`. If a stage fails, say so and stop; the next tick retries,
and a failed tick leaves the vault untouched by design.

## Validate without ingesting

```bash
python3 <this-dir>/scripts/ingest.py <transcript.md> --validate-only
```

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `MEM0_VAULT` | `~/Documents/mem0 vault` | Vault location |

## What NOT to do

- Never edit the source transcript — the pipeline copies it into the vault
- Never bypass the parser to ingest a malformed file
- Never mark a mentioned-but-unidentified person `confirmed`
