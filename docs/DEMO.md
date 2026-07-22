# Demo runbook

The claim being demonstrated: **meetings become linked vault notes without
anyone running anything.** Everything else is supporting detail.

## Before the room

```sh
./bin/loop-control.sh status          # expect: stopped
python3 skills/granola-to-obsidian-howard/scripts/vaultmerge.py   # expect: CLEAN
git -C ~/Documents/"mem0 vault" status --porcelain                # expect: empty
```

Have open: Obsidian on the vault (graph view), a terminal, and the
[vault repo commit history](https://github.com/HowieG/mem0-vault/commits/main)
in a browser.

Leave at least one un-ingested meeting in the inbox
(`~/Desktop/resources/circleback-inbox`) so the first tick has something to do.

## The demo

**1. Show the destination first.** Open the vault in Obsidian. Graph view, a
People note with its dated history, a meeting summary. This is what the loop
produces — show the output before the machinery.

**2. Point out an unconfirmed note.** Find one with the warning callout. The
point: the pipeline never guesses, and never stops to ask either. It records
what it doesn't know and keeps going.

**3. Start the loop.**

```sh
./bin/loop-control.sh start
```

**4. Stop touching the keyboard.** This is the whole demo. Within five minutes:

```sh
./bin/loop-control.sh status          # ledger lines appear
```

**5. Show the commit.** Refresh the vault repo's commit history — a
`chore(vault): automated ingest …` commit appears, authored by nobody. Refresh
Obsidian; the new notes are there.

**6. Pause the loop** before questions, so nothing surprises you mid-answer.

```sh
./bin/loop-control.sh stop
```

## Questions you will get

**"What if it gets a name wrong?"** It doesn't guess — it writes `unconfirmed`
and moves on. Show `--queue`, then `/brain-resolution` clearing one live.

**"What happens if it runs twice on the same meeting?"** Nothing. A meeting is
done when a note carries its `meeting_id`. Run a tick again and show the ledger
line: `ingested=0`.

**"Can we edit it?"** Not in v1 — one writer, everyone else pulls. If they *want*
to, that's the strongest possible signal and it's the first thing to build next.

**"Isn't this just what Circleback already does?"** Circleback stores facts per
meeting. The vault accumulates synthesis *across* meetings — merged entity
history, a navigable graph, and concepts held to a deliberately high bar.

## If something breaks

The loop is designed so a failed tick is a no-op, not a corruption. Check:

```sh
tail -20 ~/Library/Logs/mem0-meeting-ingest.log
tail -20 ~/Library/Logs/mem0-ingest-stderr.log
```

Then fall back to a foreground run, which shows everything:

```sh
MEM0_SKIP_FETCH=1 ./bin/loop-control.sh once
```
