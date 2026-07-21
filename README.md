# mem0-meeting-skills

Claude Code skills that turn meeting transcripts into a linked Obsidian vault.

Paired with the vault repo (`mem0-vault`), which holds the output. Two repos on
purpose: the ingest loop commits to the vault continuously, and that churn would
bury the history of the skills themselves.

## Skills

| Skill | Role |
|---|---|
| `granola-ingest` | Pull one meeting from Granola, write the transcript to disk, hand off |
| `granola-to-obsidian-howard` | The pipeline: copy, triage, extract, resolve speakers, write notes, verify |

## Install

```sh
./install.sh
```

Symlinks each skill into `~/.claude/skills/` and prints what it did. Re-runnable.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `MEM0_VAULT` | `~/Documents/mem0 vault` | Vault location |

Set it in your shell profile if your vault lives elsewhere:

```sh
export MEM0_VAULT="$HOME/Documents/mem0 vault"
```

## Audit

```sh
python3 skills/granola-to-obsidian-howard/scripts/vaultmerge.py   # exit 0 = clean
```

Reports broken links, stale stubs, unresolved speakers, title/filename drift, and
field conflicts. Run it after any batch of vault writes — the merge rules it
enforces have failed twice when re-derived by hand.
