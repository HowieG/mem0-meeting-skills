---
name: brain-resolution
version: 0.1.0
description: Resolve the unconfirmed people, unconfirmed companies, and Unknown company/role fields that the unattended meeting-ingest pipeline left in the Obsidian vault. Use when the vault has identity gaps to clear with a human in the loop. Triggers on "resolve the brain", "clear vault gaps", "resolve unconfirmed", "brain resolution".
---

# Brain Resolution

The interactive half of an otherwise unattended pipeline. Ingest never blocks on
a human — anything it cannot resolve lands in the vault as `status: unconfirmed`,
`Unknown` company/role fields, and a `> [!warning] Unconfirmed identity` callout.
The vault **is** the queue; there is no separate queue store. This skill walks
that queue, asks you one entity at a time, and writes the answers back through
`vaultmerge`.

## 1. Read the queue

```bash
python3 <skills-repo>/skills/granola-to-obsidian-howard/scripts/vaultmerge.py --queue
```

Exit 3 = gaps exist, exit 0 = `QUEUE EMPTY`. If empty, say so and stop — do not
go hunting for work the reader did not report.

Each entry gives you the note name, the kind, the unknown fields, the note path,
and evidence bullets lifted from the note's `## Notes` section:

| Kind | Meaning | Resolved by |
|---|---|---|
| `unconfirmed-status` | Identity itself is uncertain | Naming who it actually is |
| `unknown-field` | Person is real, `company` and/or `role` is `Unknown` | Filling the field |

## 2. Build real candidates before you ask

Never ask cold. Before each question, read `People/` and `Companies/` frontmatter
in the vault (`MEM0_VAULT`, default `~/Documents/"mem0 vault"`) for plausible
matches, and re-read the related transcripts for names that appear alongside the
gap. Those are your options. If you can only find one candidate, offer one.

## 3. Ask — one entity per call

One `AskUserQuestion` call per entity. The tool caps at 4 questions per call and
one-per-call sidesteps the cap entirely.

- `header` = the entity name.
- `question` = the evidence bullets **quoted verbatim**, then exactly what is
  unknown, then your best reading and the reasoning behind it.
- Options = real candidate answers only. Actual names, companies, roles.

Cross-note reasoning ("this profile matches the person from the Jun 18
meeting") belongs in the question text, never in an option label.

Unresolved is a valid outcome — the user expresses it by typing into the
auto-provided Other. You do not need to offer it, and offering it costs a real
candidate its slot.

## 4. Write each answer back immediately

Through `vaultmerge`, never by hand-editing frontmatter.

```python
import sys; sys.path.insert(0, "<...>/granola-to-obsidian-howard/scripts")
import vaultmerge as vm
vm.person(name, mtg, mdate, company="Mem0", role="Sales FTE",
          status="confirmed", aliases=["Eunice"], notes=["**Jul 1:** ..."])
vm.simple("Companies", name, mtg, mdate, ...)
```

Both are create-or-update and enforce the invariants: aliases merge additively,
`Unknown` upgrades to a real value, a known value never regresses to `Unknown`,
and conflicts are recorded in `vm.CONFLICTS`. Flip `status` to `confirmed` only
when the user actually identified someone — filling in a role does not confirm
an identity.

## 5. Spelling corrections keep the old rendering

Rename the note to the correct spelling **and** keep the transcript's original
rendering in `aliases`. That alias is how links written under the old spelling
keep resolving; dropping it has silently broken links before.

## 6. Don't-know answers are final for the session

If the user says they don't know, leave the note `unconfirmed` and move on. Do
not re-ask that entity in the same session, and do not rephrase it as a new
question.

## 7. Close out

1. Re-run the plain audit — `python3 .../vaultmerge.py`, exit 0 when clean.
2. Fix any links the renames broke.
3. Re-run `--queue` to show what is still outstanding.

Report: how many resolved, how many still unconfirmed, and every rename with
the alias preserved for it.

## What NOT to do

- Never offer "not sure", "skip", "leave unresolved", or any other meta-option —
  each one displaces a real candidate
- Never batch several entities into one `AskUserQuestion` call
- Never hand-edit frontmatter or the `> [!warning]` callout; go through `vaultmerge`
- Never rename a note without carrying the old spelling forward as an alias
- Never mark `confirmed` on a guess, or on a role/company fill alone
- Never re-ask an entity the user already declined to identify
- Never invent a queue outside the vault — the notes are the queue
