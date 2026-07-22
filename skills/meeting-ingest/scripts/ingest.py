#!/usr/bin/env python3
"""Ingest one normalized Circleback transcript into the Obsidian vault.

    python3 ingest.py <transcript.md> [--validate-only]

Parses (fail-loud), skips if the vault already carries this meeting_id, runs
the semantic extractor headlessly, then audits. Exit 0 means the vault is
clean and the meeting is in it. Never asks the human anything: unresolvable
identities are written `status: unconfirmed` per the pipeline skill.
"""
import argparse
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from circleback_parser import parse

SKILLS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
PIPELINE_SKILL = SKILLS_DIR / "granola-to-obsidian-howard" / "SKILL.md"
VAULTMERGE_DIR = SKILLS_DIR / "granola-to-obsidian-howard" / "scripts"

VAULT = pathlib.Path(
    os.environ.get("MEM0_VAULT", pathlib.Path.home() / "Documents" / "mem0 vault")
).expanduser()

#: Seconds before a headless extraction is abandoned. A long transcript can
#: legitimately take minutes; a stalled one must never hold the loop open.
EXTRACT_TIMEOUT = int(os.environ.get("MEM0_EXTRACT_TIMEOUT", "900"))


_MEETING_ID_KEY = re.compile(r'^meeting-id:\s*"?([^"\n]+?)"?\s*$', re.M)


def already_ingested(meeting_id, vault=None):
    """Return the summary note recording this meeting, or None.

    Deliberately narrow on two axes, both of which have bitten:

    - **Summaries only** (`glob`, not `rglob`). The extractor copies the
      transcript into Meetings/transcripts/ as its first action, and normalized
      transcripts carry `- meeting_id:` in their header. A recursive search
      calls the meeting done the moment that copy lands — so an extractor that
      dies mid-run leaves the meeting excluded forever, with no note and no
      error. A skip must never look like a success.
    - **Frontmatter key, not substring.** An id quoted in prose, or one that is
      a prefix of another id, must not count as doneness.
    """
    vault = VAULT if vault is None else pathlib.Path(vault)
    meetings = vault / "Meetings"
    if not meetings.is_dir():
        return None
    for note in sorted(meetings.glob("*.md")):
        found = _MEETING_ID_KEY.search(note.read_text(encoding="utf-8"))
        if found and found.group(1).strip() == meeting_id:
            return note.name
    return None


def extraction_prompt(meeting, path):
    return f"""Process one meeting transcript into the Obsidian vault at "{VAULT}".

Transcript file: {path}
Meeting: "{meeting.title}" ({meeting.date}), meeting_id {meeting.meeting_id},
{len(meeting.segments)} segments, speakers: {", ".join(meeting.speakers)}.

Follow the pipeline rules in {PIPELINE_SKILL} with these overrides for
unattended operation — they take precedence where they conflict:

1. NON-INTERACTIVE. You have no human. Never wait for input. Skip the
   interactive parts of Phases 4, 6 and 8 entirely.
2. Speakers are already named by diarization — treat speaker names as
   confirmed. People who are only *mentioned* in dialogue get notes only if
   substantive, with `status: unconfirmed` and the standard warning callout
   unless the transcript itself states who they are.
3. Never guess a garbled name's spelling: keep the transcript's rendering
   and record it as an alias candidate in the note body.
4. Copy the transcript into Meetings/transcripts/ first; never modify the
   original at {path}.
5. Write the meeting summary to Meetings/ with frontmatter including
   `meeting-id: "{meeting.meeting_id}"` — this key is how re-ingestion is
   prevented, it is not optional.
6. All entity notes (People/Companies/Concepts/Projects) are written through
   vaultmerge, not hand-rolled: add {VAULTMERGE_DIR} to sys.path and use
   vm.person() / vm.simple(). Respect the concept bar: 0-2 concepts, only
   transferable decision rules with meeting-specific evidence.
7. Finish by running the audit (python3 {VAULTMERGE_DIR}/vaultmerge.py) and
   fixing any broken links you introduced.

Report at the end: notes created/updated, unconfirmed entities left behind.
"""


def run_extractor(meeting, path):
    """Headless claude extraction followed by the vault audit. Returns 0 iff
    both succeeded; verifying that the meeting actually landed is the
    caller's job (the vault alone is authoritative)."""
    source = pathlib.Path(path).resolve()
    try:
        result = subprocess.run(
            ["claude", "-p", extraction_prompt(meeting, source),
             "--add-dir", str(VAULT),
             # The transcript lives outside the vault, and under launchd the
             # cwd is /. Without this the extractor cannot read its own input.
             "--add-dir", str(source.parent),
             "--allowedTools", "Read", "Write", "Edit", "Glob", "Grep",
             "Bash(python3:*)", "Bash(ls:*)", "Bash(cp:*)"],
            text=True, timeout=EXTRACT_TIMEOUT)
    except subprocess.TimeoutExpired:
        # Unbounded, one stalled call blocks every later tick: launchd will not
        # start a second instance of a job already running under this label, so
        # the loop would go quiet — indistinguishable from "no new meetings".
        print(f"extraction timed out after {EXTRACT_TIMEOUT}s — "
              "meeting left un-ingested, will retry next tick", file=sys.stderr)
        return 1
    if result.returncode != 0:
        print(f"extraction failed (exit {result.returncode})", file=sys.stderr)
        return result.returncode

    audit = subprocess.run(
        [sys.executable, str(VAULTMERGE_DIR / "vaultmerge.py")])
    if audit.returncode != 0:
        print("audit FAILED after ingest — vault needs attention", file=sys.stderr)
    return audit.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    meeting = parse(args.transcript)
    print(f"parsed: {meeting.title!r} [{meeting.meeting_id}] "
          f"{len(meeting.segments)} segments, {len(meeting.speakers)} speakers")

    if args.validate_only:
        return 0

    existing = already_ingested(meeting.meeting_id)
    if existing:
        print(f"already ingested ({existing}) — nothing to do")
        return 0

    rc = run_extractor(meeting, args.transcript)
    if rc != 0:
        return rc

    if not already_ingested(meeting.meeting_id):
        print("extraction completed but no note carries the meeting_id — "
              "ingest NOT recorded, will re-run next time", file=sys.stderr)
        return 1

    print(f"ingested {meeting.meeting_id}: audit clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
