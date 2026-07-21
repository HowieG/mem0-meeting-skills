---
name: granola-ingest
version: 1.0.0
description: Pick a meeting from Granola, save its transcript to a file, and run the vault pipeline on it. Use when the user wants to ingest a Granola meeting into Obsidian. Triggers on "ingest a meeting", "pull a meeting from granola", "ingest from granola".
triggers:
  - ingest a meeting
  - pull a meeting from granola
  - ingest from granola
  - granola ingest
---

# Granola Ingest

Front-end for [[granola-to-obsidian-howard]]. Picks a meeting from Granola, writes
its transcript to disk, then hands off. That is the whole job — the vault work
belongs to the other skill.

There is **no MCP tool that exports to a file.** The Granola MCP surface is six
read tools; saving is you calling `Write` with what `get_meeting_transcript`
returns.

## Step 1 — Pick the meeting

```
mcp__claude_ai_Granola__list_meetings(time_range="last_30_days")
```

Present the results with `AskUserQuestion` — title and date per option. Widen with
`time_range="custom"` plus `custom_start`/`custom_end` if the meeting is older.

Do not filter the list against what is already in the vault unless asked. Re-ingesting
is the user's call, not a guardrail worth building.

## Step 2 — Fetch and save

```
mcp__claude_ai_Granola__get_meeting_transcript(meeting_id=<uuid>)
```

Returns `{id, title, transcript}` where `transcript` is a **single string with
`\n` between speaker turns** — write it out with real newlines, not as one line.

Save to the **transcript source directory**, alongside the existing originals —
not into the vault:

```
~/Desktop/resources/granola-transcripts/YYYY-MM-DD-<slug>.transcript.md
```

This file is the original. It is written once and never edited again: Phase 1
copies it into the vault, and every later edit — speaker substitution, spelling
correction — happens to that copy. Keeping a pristine local record means a botched
substitution is recoverable by diff or re-copy without another API round-trip, and
it survives anything that happens to the Granola record.

Slug from the title: lowercase, hyphenated, drop filler. Date from the
`list_meetings` metadata, not from today.

Write a four-line header above the transcript body:

```markdown
# <Title> — Transcript

- **Date:** <date from list_meetings>
- **Granola title:** <title>
- **Meeting ID:** <uuid>
- **Participants:** <known_participants from list_meetings>

---

<transcript body>
```

This is not reformatting for its own sake — the pipeline reads `Date` and
`Meeting ID` for summary frontmatter, and the ID is the only stable key tying a
vault note back to the Granola record. Everything below the `---` is verbatim.

## Step 3 — Hand off

Invoke `granola-to-obsidian-howard` on the file just written, **from Phase 1**.

Nothing about the pipeline changes. Once the transcript is on disk it is
indistinguishable from one that was always there: Phase 1 copies it into
`Meetings/transcripts/`, and the originals-unmodified check at Phase 7 is a real
check against a real file. Fetching is the only thing this skill adds.

Downstream in full: copy, triage, extract, resolve speakers interactively, write
notes at the high bar, confirm spellings, verify, resolve open questions, report.

## Notes on the transcript format

- Speaker labels are `Speaker A`/`Speaker B`/... exactly as the pipeline expects.
- The string starts with `Microphone: ` before the first speaker label —
  `Microphone` is the note-taker's own audio, so the first turn is the user's.
  Treat it as one corroborating signal for that speaker, never as proof, and still
  ask in Phase 4.
- `known_participants` reliably lists **only the note creator**. It will not
  resolve the other speakers for you.

## What NOT to do

- Never claim an MCP tool saved the file — you wrote it
- Never write the fetched transcript straight into the vault; it goes to the
  source directory and Phase 1 copies it in
- Never edit the fetched original after writing it — all edits target the vault copy
- Never skip Phase 4 because `Microphone` identified one speaker
