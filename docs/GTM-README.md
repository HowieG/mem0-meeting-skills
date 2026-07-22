# Reading the Mem0 meeting vault

The vault is a set of linked notes built automatically from Circleback meeting
transcripts: one summary per meeting, plus notes for the people, companies,
projects, and ideas that came up. Everything is plain Markdown in a git repo,
so reading it needs nothing but git and Obsidian.

## One-time setup

1. **Install [Obsidian](https://obsidian.md)** (free).

2. **Clone the two repos.** Both are private — ask Howard for access first.

   ```sh
   git clone git@github.com:HowieG/mem0-meeting-skills.git
   git clone git@github.com:HowieG/mem0-vault.git ~/Documents/"mem0 vault"
   ```

3. **Run the installer.**

   ```sh
   cd mem0-meeting-skills && ./install.sh
   ```

   It links the skills into Claude Code, checks the vault, and runs the
   consistency audit. It's safe to run again any time.

4. **Open the vault in Obsidian** — *Open folder as vault* →
   `~/Documents/mem0 vault`.

## Getting updates

New meetings are ingested automatically on Howard's machine and pushed to the
vault repo. To pull them:

```sh
git -C ~/Documents/"mem0 vault" pull
```

Obsidian picks up the changes without a restart.

## Reading it

- **`Meetings/`** — one summary per meeting: what was discussed, decisions,
  action items, attendees. `Meetings/transcripts/` holds the full text.
- **`People/`** — one note per person, with their company, role, and a dated
  history of every meeting they've appeared in.
- **`Companies/`** — accounts, vendors, and prospects, with what each meeting
  said about them.
- **`Concepts/`** and **`Projects/`** — ideas and workstreams worth tracking
  across meetings.

Use the **graph view** (the sidebar icon) to see how accounts, people, and
projects connect. Backlinks at the bottom of any note show everywhere it's
mentioned.

### What "unconfirmed" means

Notes marked `status: unconfirmed`, or with `Unknown` company/role, carry a
warning callout:

> [!warning] Unconfirmed identity

The pipeline writes these deliberately rather than guessing. Someone mentioned
by first name only, or a company the transcript garbled, stays flagged until a
human confirms it. **Treat an unconfirmed note as a lead, not a fact.**

## Found something wrong?

For v1, **Howard is the only writer** — please don't commit to the vault
directly. Send him the note name and what's wrong, and he'll fix it at the
source so the correction survives the next automated run.

Editing your own local copy is fine for scratch work, but `git pull` will
conflict with it later.
