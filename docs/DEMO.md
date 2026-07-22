# Demo runbook

The claim: **a meeting you just recorded becomes linked vault notes, and a git
commit, without anyone running anything.**

## Use `/loop`, not routines

| | `/loop` (in-session) | Routines (scheduled cloud agents) |
|---|---|---|
| Runs | Locally, in your Claude Code session | In the cloud |
| Local vault at `~/Documents/mem0 vault` | ✅ reachable | ❌ not on that machine |
| Circleback MCP | ✅ your live OAuth session | ⚠️ interactive auth often absent headless |
| Survives closing Claude Code | ❌ session-only | ✅ |

**Routines cannot work for v1** — the vault is a local filesystem path a cloud
agent has no access to, and the Circleback MCP is interactively authenticated.

`/loop` has a second advantage: the loop *is* an agent, so it calls
`SearchMeetings` / `GetTranscriptsForMeetings` directly. No nested headless run
just to reach MCP.

Two `/loop` caveats: ticks fire **only while the session is idle** (so stop
typing at Claude during the demo), and jobs die when the session closes.

> **Path to routines later:** the vault is a git repo, so a cloud agent could
> clone → ingest → push without touching this machine. The blocker is
> Circleback auth in a headless context, not the vault.

## Before the room

**1. Confirm a clean, healthy starting state.**

```sh
cd ~/Desktop/resources/mem0-meeting-skills
python3 skills/granola-to-obsidian-howard/scripts/vaultmerge.py   # expect: CLEAN
git -C ~/Documents/"mem0 vault" status --porcelain                # expect: empty
```

**2. Record a short Circleback meeting ~5 minutes before you start.** Say a few
substantive things — a decision, a name, a company — so the extracted notes have
something real in them. A meeting of pleasantries produces a thin, boring note.

**3. Confirm Circleback has processed it.** Transcription lags the call by
minutes; this is the single most likely thing to go wrong.

Ask Claude: *"Search Circleback for meetings from today and show me the
transcript for the most recent one."* You need actual transcript segments back,
not just a meeting record. **If the transcript isn't ready, the loop correctly
does nothing** — wait, don't debug.

**4. Open three windows:** Obsidian on the vault, a terminal, and
https://github.com/HowieG/mem0-vault/commits/main.

## The demo

**Step 1 — Show the destination before the machinery.** In Obsidian: the graph,
a People note with dated cross-meeting history, a meeting summary. Nobody cares
about the pipeline until they want the output.

**Step 2 — Show an `unconfirmed` note.** Find the ⚠️ callout. *It never guesses,
and it never stops to ask either — it records what it doesn't know and keeps
going.* This is the decision that makes unattended operation possible, and it's
what a sharp person will probe.

**Step 3 — Start the loop.**

```
/loop 5m Run one meeting-ingest tick per the "Unattended tick" section of the meeting-ingest skill.
```

**Step 4 — Stop touching the keyboard.** This is the demo. Ticks only fire when
the session is idle, so talk to the room, not to Claude. Within five minutes the
meeting you just recorded is fetched, ingested, committed, and pushed.

**Step 5 — Show the commit.** Refresh the GitHub commits page: a
`chore(vault): automated ingest …` commit, authored by nobody. Refresh Obsidian —
the new notes are linked into the existing graph.

**Step 6 — Pause before questions**, so nothing surprises you mid-answer: tell
Claude to stop the loop.

## The four questions you'll get

| Question | Answer | Show them |
|---|---|---|
| "What if it gets a name wrong?" | It doesn't guess — writes `unconfirmed` and moves on | `vaultmerge.py --queue`, then `/brain-resolution` clearing one live |
| "What if it runs twice on the same meeting?" | Nothing. Done = a summary note carries its `meeting_id` | Next tick's ledger line: `ingested=0` |
| "Can we edit it?" | Not in v1 — one writer, everyone pulls | If they *want* to, that's your best signal, and it's next |
| "Isn't this what Circleback does?" | Circleback stores facts *per meeting*; the vault accumulates synthesis *across* meetings | The graph, and a People note spanning several meetings |

## If something breaks

A failed tick is a no-op by design, never a corruption.

```sh
tail -20 ~/Library/Logs/mem0-meeting-ingest.log
```

Fallback, in order:

```sh
# 1. Ingest a transcript already on disk (skips Circleback entirely)
MEM0_SKIP_FETCH=1 ./bin/ingest-tick.sh

# 2. Ingest one specific file, with full output
python3 skills/meeting-ingest/scripts/ingest.py <transcript.md>
```

**Have a backup transcript in `~/Desktop/resources/circleback-inbox/`** that is
*not* yet ingested. If the live meeting's transcript isn't ready in time, fall
back to option 1 and the demo still lands — the only thing you lose is the
"meeting I recorded five minutes ago" moment.
