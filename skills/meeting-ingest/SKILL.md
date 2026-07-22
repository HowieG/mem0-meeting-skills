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

One tick = fetch new meetings, ingest them, publish the vault. Run it with:

```
/loop 5m Run one meeting-ingest tick per the "Unattended tick" section of the meeting-ingest skill.
```

You are an agent, so **you** make the Circleback MCP calls directly — there is
no nested headless run for fetching. Do exactly this, and nothing else:

1. `SearchMeetings` with `pageIndex: 0`, `startDate` = `INGEST_WINDOW_DAYS`
   (default 7) before today, `endDate` = today.
2. For each result, check whether any file under `<vault>/Meetings/` already
   contains its id. Skip those — already ingested. **This check is the only
   thing preventing double-ingestion; never skip it.**
3. `GetTranscriptsForMeetings` for the ids that remain (batch, ≤50 per call).
4. Write each one to the inbox using the project's normalizer — never
   hand-roll the format:

   ```python
   import sys; sys.path.insert(0, "<this-dir>/scripts")
   from circleback_fetch import write_transcript
   write_transcript(meeting_dict, transcript_list, inbox_dir)
   ```

   An empty transcript means Circleback is still processing. `write_transcript`
   returns `None` and writes nothing — correct. A partial file would let the id
   filter mark the meeting done forever.
5. Run the batch ingester, which spawns an isolated headless extraction per
   meeting so a long transcript never floods this session's context:

   ```bash
   python3 <this-dir>/scripts/batch.py <inbox_dir> --window-days 7
   ```

6. If `<vault>` has changes, commit (`chore(vault): automated ingest <stamp>`)
   and push. If it has none, **make no commit** — a quiet tick must leave no
   trace in git history.
7. Report one line: meetings fetched, ingested, skipped, and whether you pushed.

Never ask the user anything during a tick. Gaps are written into the vault as
`status: unconfirmed` and cleared later by `brain-resolution`.

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
