---
name: granola-to-obsidian-howard
version: 1.0.0
description: Turn Granola transcripts into Obsidian vault notes with interactive speaker resolution. Use when processing, summarizing, or extracting from Granola meeting transcripts. Triggers on "parse the transcripts", "summarize meetings", "process these transcripts", "granola transcripts".
triggers:
  - parse the transcripts
  - summarize meetings
  - process these transcripts
  - granola transcripts
  - meeting summaries
---

# Granola to Obsidian (Howard)

Turns Granola meeting transcripts into a linked Obsidian vault. Three rules carry
most of the weight: **never modify original transcripts**, **resolve anonymous
speakers interactively rather than guessing**, and **hold a high bar for creating
notes** — a sparse vault of real insight beats a dense one of clichés.

## Locating the vault

`fd`/`find` cannot see `~/Documents` — macOS TCC blocks shell access. Read the
registry instead:

```bash
cat ~/Library/Application\ Support/obsidian/obsidian.json
```

Vault layout used here:

```
Meetings/              summaries
Meetings/transcripts/  working copies (speaker-resolved)
People/  Concepts/  Projects/  Companies/
```

`Companies/` matters more than it looks: without it, every org and tool wiki-link
dangles. In one run that was 25 broken links, `Mem0` alone accounting for 25
references.

---

## Phase 1 — Copy transcripts (never edit originals)

Copy each transcript into `Meetings/transcripts/` **before touching anything**.
All later edits — speaker substitution especially — happen to the copy. The
original stays byte-identical.

```bash
cp <source>/*.transcript.md "$VAULT/Meetings/transcripts/"
```

Confirm with `diff` after processing that the originals are unchanged.

## Phase 2 — Triage

Skip and log: empty stubs, <20 words of real content, garbled recordings,
scheduling-only fragments, medical/personal appointments, recording-setup talk.
Sparse but substantive notes still get processed.

## Phase 3 — Extract in parallel

One subagent per transcript. Files >50K: instruct chunked reads via offset/limit.

Granola transcripts in this vault are usually **not** the YAML-frontmatter
format — expect a plain header block (Date, Granola title, Meeting ID,
Participants) and anonymous `Speaker A/B/C`. Only the note creator is named.

Agent rules, non-negotiable:

- Never fabricate. Extract only what is in the transcript.
- Never guess a Speaker→name mapping. Record the letter, plus any identity
  evidence found (see Phase 4).
- Never attribute an action item to an owner unless ownership is explicit.
- Agents do **not** write to People/Concepts/Projects/Companies — they return
  extracted entities as JSON. Consolidation is serial, or concurrent agents
  race and create the duplicate notes this skill forbids.

Have each agent additionally return, per unresolved speaker, **2–4
identity-revealing quotes** — lines where the speaker states their role, claims
ownership, references their own history, or is addressed by others. Generic
opinions are useless here; "since I'm the sales guy, I'm the owner of
everything" is what you want.

## Phase 4 — Resolve speakers interactively (REQUIRED)

Do this **after** all extraction, before writing any notes. Never skip it and
never guess your way past it.

Work **one speaker at a time, meeting by meeting** — a separate
`AskUserQuestion` call for each. The tool's 4-question cap is per *call*, so
one call per speaker sidesteps it entirely. Resolve a speaker fully before
asking about the next.

Each call is shaped like this:

- **`header`** — the speaker letter (`Speaker A`).
- **`question`** — the meeting date and title, then **~10 identity-revealing
  lines of that speaker's speech**, then your best guess and the reasoning
  behind it.
- **`options`** — **names, and nothing else.** The user answers by typing the
  real name into the auto-provided **Other**; the options exist only to save
  that typing when a candidate is already on file.

Build the option list in this order:

1. **Existing `People/` notes** whose recorded role, company, or context
   plausibly matches the evidence. Read their frontmatter first — `ls People/`
   then check `role:` and `company:`. Most likely candidate first.
2. **Names spoken in this transcript** but not yet mapped to a speaker. If the
   dialogue says "let me ask Disha" and nobody has been matched to Disha, that
   is a real candidate.
3. Only if fewer than two names exist anywhere (a fresh vault, an early run),
   fall back to a single non-name option to satisfy the tool's two-option
   minimum — and say plainly in the question that nothing on file matches.

Never offer meta-options — "not sure", "leave unresolved", "same as the speaker
from the other meeting". They are not answers to *who is this*, and each one
displaces a real name. Unresolved is still a valid outcome: the user says so in
**Other**, and the speaker keeps their letter.

Cross-meeting identity ("this profile matches Speaker A from Jun 18") is
**reasoning, and belongs in the question text**, never in an option.

Choosing the 10 lines is the part that matters. Take lines where the speaker
states a role, claims ownership, references their own history or contract, or
is addressed by someone else. Generic opinions identify nobody — *"yeah, that
makes sense"* is worthless here, *"since I'm the sales guy, I'm the owner of
everything"* is the whole game. Quote verbatim; never paraphrase into the
question.

Ask about ambiguous companies and first-name-only people the same way, one call
each, after the speakers are done.

Ask about ambiguous **companies and first-name-only people** in the same pass.
Present what the transcript says and let the user correct it.

Carry the answers through everywhere:

1. **Rewrite the working copy** in `Meetings/transcripts/` — substitute
   `Speaker A:` → `Howard Gil:` throughout. The original on disk is untouched;
   this copy becomes readable.
2. **Update summary frontmatter** — `attendees` and `related` get the real
   names, not letters.
3. **Update summary bodies** — People tables, action-item owners, quote
   attributions.
4. **Create People notes** with `status: confirmed` for anyone the user named.
   Only people never resolved stay `unconfirmed`.

If the user doesn't know who a speaker is, leave the letter in place and mark
the note `unconfirmed`. An honest gap beats a confident wrong name.

## Phase 5 — Write notes (high bar)

The natural rate is ~6 concepts per meeting. That is far too many — most are
industry clichés or restatements of a single decision. Calibration from a real
run: 4 meetings yielded **8 concepts**, not 26.

### Concepts — default is NOT to create one

Create a Concept note only if **all four** hold:

1. It is a transferable decision rule or model — it would change how you decide
   something in a *different* context.
2. The meeting supplied specific reasoning or evidence for it, not just the
   phrase.
3. You could not have written the note without attending. If it's writable from
   general knowledge, it's a cliché.
4. It isn't already covered by an existing note — enrich that one instead.

Reject on sight: `Fail Fast`, `MVP`, `Dogfooding`, `Product-Market Fit`,
`Show vs Tell`, `Do It By Hand Before Automating`, and anything else a reader
could define without the meeting. Reject restatements of one meeting's decision
("Decouple Launch from Product") — that belongs in the summary and the Project
note, not a standalone concept.

**Cap: 0–2 concepts per meeting.** Zero is a perfectly good answer. If you have
five candidates, keep the one with the sharpest evidence.

Worth keeping, for calibration: `Point-of-View Selling` (specific mechanism —
pull 10-Ks, classify cost-saving vs growth, pitch a financial thesis),
`Measure-Then-Enable Pilot` (concrete two-month structure), `Supply and Demand
of Memory` (a real strategic objection plus its answer).

### Companies — only with meeting-specific substance

Create a note for clients, vendors under evaluation, investors, and
acquisition targets — entities the meeting says something *particular* about.

Do **not** create notes for ubiquitous tools and platforms — `Claude`,
`ChatGPT`, `Google`, `Meta`, `Stripe`, `Slack` — unless the meeting makes a
specific, non-obvious claim about them. A note reading "Anthropic's assistant"
is pure noise. A dangling `[[Claude]]` link is better than a content-free note;
Obsidian treats unresolved links as future notes.

### People

One note per person. Merge name variants across meetings only on real evidence
(same role, same context), and record the merge in an `> [!note] Entity
resolution` callout stating what was assumed and what to split if wrong. Weak
merges must say so.

`status: confirmed` only for people the user identified in Phase 4 or who are
named outright in the transcript.

### Projects

Products, tools, ventures, and workstreams discussed. Merge across meetings
when they're the same effort at different stages.

### Merging into existing notes

Once more than one meeting is in the vault, most writes are **updates, not
creates**. An update must append the new meeting to `related:`, add a dated
bullet under `## Notes` (`**Jul 6:** ...` — undated bullets become ambiguous the
moment a note spans two meetings), and bump `last-contact` only if the new
meeting is later.

**Carry aliases through every merge.** A merge that omits them silently drops
the alias list, which breaks every link written under the old spelling — and the
link check is the only thing that catches it. This has actually happened: a
`Parush` alias was lost on merge and broke three links from a summary that had
been correct when written.

**Upgrade placeholder fields when a later meeting knows better.** The first
meeting to mention someone often yields `company: Unknown` / `role: Unknown`. A
later meeting frequently identifies them properly — and a merge that only appends
notes leaves the stub's frontmatter wrong forever, while the body says otherwise.
This has happened too: a person was `company: Unknown` after one meeting
established he was a mem0 sales FTE running client demos.

Merge fields by this rule:

| Situation | Action |
|---|---|
| Existing is `Unknown`/empty, new has a value | **Overwrite** |
| Existing is specific, new is `Unknown` | **Keep existing** — never regress to Unknown |
| Both specific and they agree | Keep |
| Both specific and they **conflict** | Keep existing, and raise it in Phase 8 — a conflict usually means two people shared a note, or a role changed |

Same for `status`: `unconfirmed` → `confirmed` on identification, never the
reverse. And `last-contact` moves forward only.

**These rules are implemented in `scripts/vaultmerge.py` — use it rather than
re-deriving them.** Both failures above happened while hand-rolling the merge.

```python
import sys; sys.path.insert(0, "/Users/howardgil/.claude/skills/granola-to-obsidian-howard/scripts")
import vaultmerge as vm

vm.person("Younes", mtg, mdate, company="Mem0", role="Sales FTE",
          aliases=["Eunice"], notes=["**Jul 1:** ran the CBRE demo."])
vm.simple("Companies", "Wiser", mtg, mdate, kind="tool", desc="...")
vm.report(vm.audit())          # exit 0 = clean
```

`person()` and `simple()` are create-or-update: they append to `related:`,
add dated note bullets, merge aliases additively, upgrade placeholder fields, and
record conflicts in `vm.CONFLICTS` for Phase 8. A name that appears in several
meetings and is still `Unknown` is usually a merge that silently no-opped, not a
genuine mystery.

## Phase 6 — Confirm spellings (REQUIRED)

Granola mangles proper nouns, and the mangled form is often the *only* form in
the transcript — you cannot infer the right spelling from the audio. Confirmed
examples from this vault: `Taranjit` → **Taranjeet**, `Dax` → **Dex**,
"Harvard" → Howard, "Menzero" → Mem0, "Kanah" → Kunal, "Elan Gil" → Elad Gil,
and `Parush`/`Porosh`/`powerush` for one person.

Do this **after the notes are written**, so the roster you present is the real
set of notes on disk.

Present every proper noun that got a note — People and Companies — grouped by
folder, each with the transcript's rendering and every variant seen:

```
People
  Taranjit    (only spelling in transcript)
  Dax         (also "Dex" in the Jun 18 meeting)
  Porosh      (also "Parush", "powerush")

Companies
  Mem0        (also "Menzero", "M0")
```

Take corrections as **free text in one message** — spelling fixes are usually
few, and a dozen `AskUserQuestion` calls to change two names is worse than a
list. Use `AskUserQuestion` only when you have a specific alternative to
propose for a specific name.

Then propagate every correction:

1. **Rename the note file** to the corrected spelling.
2. **Keep the transcript's spelling as an alias** in frontmatter — never drop
   it. It is how the garbled form stays searchable, and how a later run
   auto-matches the same person without asking again.
3. **Rewrite wiki-links** across every note in the vault.
4. **Correct the transcript copy.** It already carries substituted speaker
   names, so it is not a verbatim record — a misspelled name in it is just an
   error. The original on disk stays untouched regardless.
5. **Re-run the link check** afterwards; renames are the easiest way to break
   links.

Never silently correct a name you merely suspect is wrong. Ask, then fix
everywhere at once.

## Phase 7 — Verify

Run the audit — do not hand-roll these checks. Re-deriving the link checker by
hand has produced a broken regex and a missing-module crash on separate runs, and
a hand-rolled check cannot see the title/filename drift that aliases mask.

```bash
python3 ~/.claude/skills/granola-to-obsidian-howard/scripts/vaultmerge.py   # exit 0 = clean
```

It reports, in one pass:

- **broken links** — case-insensitive, alias-aware, naming the files they sit in
- **stale stubs** — People in 2+ meetings still carrying `Unknown` company/role
- **unresolved speakers** — raw `Speaker X:` labels left in any transcript
- **title/filename mismatch** — e.g. `Dax.md` whose frontmatter says `Dex`. Links
  still resolve through the alias, so nothing looks wrong until the note is
  renamed or the alias is dropped
- **field conflicts** — two meetings asserting different company/role

Dangling links are acceptable when the target isn't worth a note — say which ones
and why, don't silently create stubs to zero out the number.

Confirm originals are unmodified:

```bash
diff -q <original> "$VAULT/Meetings/transcripts/<copy>"  # expect: differs only by speaker names
```

## Phase 8 — Resolve open questions (REQUIRED)

Processing always leaves loose ends that only the user can close. Do not bury
them in prose at the end of a long report — they get skimmed past. Put each one
in an `AskUserQuestion`, batching up to the four-question cap per call while each
stays legible. Unlike speaker resolution these rarely need ten lines of quoted
context, so they batch comfortably; split them out when one needs real evidence
to be answerable.

What qualifies as an open question:

- **An unidentifiable entity that clearly matters.** A competitor whose name the
  transcript garbles beyond recovery ("Nessie" / "Nessilab" / "Desi Labs"), a
  client mentioned once with real money attached, a tool nobody named.
- **A possible duplicate you refused to merge.** Two notes that may be one person
  where the evidence cuts both ways — e.g. `TJ` and `Taranjeet`, where the
  nickname fits but one meeting has them apparently distinct.
- **A merge you made on weak evidence.** Say what you assumed and offer the split.
- **A deliberate dangling link.** If you left `[[X]]` unresolved because X didn't
  merit a note, confirm that judgment rather than silently shipping a broken link.
- **A contradiction between meetings.** The same decision recorded two ways, or a
  risk raised and never resolved across several transcripts.

Shape each call the way Phase 4 shapes a speaker question: state the evidence,
quote the transcript verbatim where it is the whole point, give your read, and
make the options real answers rather than "yes/no/not sure". For an unidentified
company, offer the candidate spellings you actually saw. For a possible duplicate,
offer merge / keep separate.

Ask only about things that change the vault. A question whose answer alters
nothing is noise — resolve it yourself and move on.

Apply every answer immediately: create the missing note, merge the duplicate and
alias the old name, or unlink the reference. Then re-run the Phase 7 link check,
since merges and renames break links.

## Phase 9 — Report

Table of meetings: date, speakers resolved, action items, notes created, status.
State what was skipped and why, and every merge that was made on weak evidence.

**Never publish anything externally** — no social posts, no sending, no sharing —
without explicit authorization for that specific act. Writing to the vault is the
whole job.

---

## What NOT to do

- Never modify an original transcript — work on the copy in the vault
- Never guess a speaker's identity — ask, or leave it unresolved
- Never put anything but a name in a speaker-resolution option — no "not sure",
  no "leave unresolved", no cross-meeting pointers
- Never silently correct a garbled name — confirm it in Phase 6, then fix it
  everywhere and keep the transcript's spelling as an alias
- Never drop aliases when merging into an existing note — it breaks links that
  were correct when written
- Never leave open questions buried in the final report — Phase 8 asks them
- Never publish externally without authorization for that specific act
- Never fabricate action-item ownership
- Never create a Concept note that passes fewer than all four tests
- Never create Company notes for ubiquitous tools
- Never let parallel agents write graph notes — consolidate serially
- Never post externally
