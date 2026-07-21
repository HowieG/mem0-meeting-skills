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
