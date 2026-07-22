# mem0-meeting-skills

Turns Circleback meeting transcripts into a linked Obsidian vault — unattended.

Paired with the vault repo ([`mem0-vault`](https://github.com/HowieG/mem0-vault)),
which holds the output. Two repos on purpose: the ingest loop commits to the
vault continuously, and that churn would bury the history of the code.

**Reading the vault?** You want [`docs/GTM-README.md`](docs/GTM-README.md), not
this file.

## How it works

```
launchd (5 min)
   │
   ├─ fetch    Circleback MCP → normalized transcripts in the inbox
   ├─ ingest   parse → skip if already in vault → headless extractor → audit
   └─ publish  commit + push the vault, only if it changed
```

Two layers, deliberately split:

- **Python owns what must be correct** — parsing, the identity filter, the
  ledger, the audit. Deterministic and unit-tested.
- **A headless Claude run owns what must be judged** — triage, entity
  extraction, writing notes at the pipeline's quality bar.

### It never blocks

The loop has no human in it. Anything the extractor cannot resolve — a person
named only by first name, a garbled company — is written into the vault as
`status: unconfirmed` with `Unknown` fields and a warning callout. **The vault
is the queue.** There is no separate state store, nothing to resume, and a
tick always runs to completion.

A human clears those gaps later, whenever convenient, with `/brain-resolution`.

### It can't double-ingest

A meeting is done if and only if a note under `Meetings/` carries its
`meeting_id`. There is no watermark and no timestamp cursor — transcripts
arrive minutes-to-hours after a call ends, and a cursor that advanced past a
not-yet-transcribed meeting would drop it silently and forever.

## Skills

| Skill | Role |
|---|---|
| `meeting-ingest` | Parse and ingest one transcript; the unattended path |
| `granola-to-obsidian-howard` | The pipeline: triage, extract, write notes, verify |
| `brain-resolution` | Interactive: clear the unconfirmed/Unknown gaps |
| `granola-ingest` | Granola source adapter (retained, unused in v1) |

## Install

```sh
./install.sh            # symlink skills, check vault, run audit
./install.sh --clone    # also clone the vault if missing
```

## Running the loop

```sh
./bin/loop-control.sh start     # launchd agent, ticks every 5 min
./bin/loop-control.sh stop      # pause it
./bin/loop-control.sh once      # one tick, in the foreground
./bin/loop-control.sh status    # loaded? plus recent ledger lines
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `MEM0_VAULT` | `~/Documents/mem0 vault` | Vault location |
| `MEM0_TRANSCRIPTS` | `~/Desktop/resources/circleback-inbox` | Where fetched transcripts land |
| `INGEST_WINDOW_DAYS` | `7` | How far back each tick looks |
| `MEM0_LEDGER` | `~/Library/Logs/mem0-meeting-ingest.log` | Run log |
| `MEM0_SKIP_FETCH` | unset | `1` ingests the inbox without calling Circleback |

The ledger lives outside the vault on purpose: a quiet tick must leave the
vault byte-identical so the publish stage makes no commit.

## Tests

```sh
python3 -m unittest discover -s tests
```

Stdlib `unittest`, no dependencies. Tests use temp directories — they never
touch the real vault.

## Audit

```sh
python3 skills/granola-to-obsidian-howard/scripts/vaultmerge.py           # exit 0 = clean
python3 skills/granola-to-obsidian-howard/scripts/vaultmerge.py --queue   # exit 3 = gaps
```

The audit checks consistency (broken links, field conflicts, title drift).
`--queue` is a different question — *what needs a human* — and is deliberately
broader: it reports single-meeting entities the audit's stale-stub check
ignores.

## Known limits (v1)

- **Single writer.** Concurrency is deliberately unhandled; one machine runs
  the loop and everyone else pulls.
- **Circleback only.** The driver is shaped for other sources; only one ships.
- **No tombstones.** A thin or missing transcript is skipped and retried on the
  next tick rather than recorded as permanently skipped.
- **Polling, not webhooks.** The five-minute timer is demo plumbing; Circleback
  fires a meeting-end webhook that should replace it.
