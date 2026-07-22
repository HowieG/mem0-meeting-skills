#!/usr/bin/env python3
"""Idempotent batch ingest of normalized Circleback transcripts.

    python3 batch.py <source_dir> [--window-days N] [--dry-run]

Scans source_dir for transcripts dated within the window and ingests only
meetings whose meeting_id appears nowhere under vault/Meetings/. The vault
alone is authoritative — no watermarks, no timestamps, no state files.
"""
import argparse
import datetime
import os
import pathlib
import sys
from dataclasses import dataclass, field

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import ingest
from circleback_parser import ParseError, parse
from ingest import already_ingested


THIN_TRANSCRIPT_WORDS = 20


@dataclass(frozen=True)
class Candidate:
    path: pathlib.Path
    meeting: object = None
    error: str = None


@dataclass
class BatchResult:
    ingested: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    would_ingest: list = field(default_factory=list)
    already_present: int = 0


def find_candidates(source_dir, window_days, today):
    """Transcripts in source_dir dated within window_days of today.

    Files that fail to parse (or carry an unreadable date) are still
    candidates, classified as errors so the run can report them as skips.
    """
    candidates = []
    for path in sorted(pathlib.Path(source_dir).glob("*.md")):
        try:
            meeting = parse(path)
        except ParseError as exc:
            candidates.append(Candidate(path, error=str(exc)))
            continue
        try:
            meeting_date = datetime.date.fromisoformat(meeting.date)
        except ValueError:
            candidates.append(Candidate(
                path,
                error=f"{path.name}: unreadable header date {meeting.date!r}"))
            continue
        if abs((today - meeting_date).days) <= window_days:
            candidates.append(Candidate(path, meeting=meeting))
    return candidates


def filter_new(candidates, vault):
    """Keep candidates whose meeting_id appears in no file under vault/Meetings/.

    Error candidates pass through — they carry no meeting_id to check and the
    run reports them as skips. Presence of the id in a Meetings note is the
    only doneness signal; there is no other state.
    """
    vault = pathlib.Path(vault)
    return [c for c in candidates
            if c.meeting is None
            or not already_ingested(c.meeting.meeting_id, vault)]


def run_batch(source_dir, vault, extractor, window_days=7, today=None,
              dry_run=False, ledger=None):
    """One idempotent tick: ingest every new candidate, ledger the outcome.

    The extractor is injected — production wraps the headless claude call
    from ingest.py. Success is judged only by the vault: after each extractor
    call the meeting_id must appear under vault/Meetings/, else the meeting
    counts as failed and will be retried next tick.
    """
    if today is None:
        today = datetime.date.today()
    vault = pathlib.Path(vault)

    candidates = find_candidates(source_dir, window_days, today)
    new = filter_new(candidates, vault)
    result = BatchResult(already_present=len(candidates) - len(new))

    for candidate in new:
        if candidate.error is not None:
            result.skipped.append(candidate.error)
            continue
        words = sum(len(seg.text.split()) for seg in candidate.meeting.segments)
        if words < THIN_TRANSCRIPT_WORDS:
            result.skipped.append(
                f"{candidate.path.name}: thin transcript "
                f"({words} words of segment text)")
            continue
        if dry_run:
            result.would_ingest.append(candidate.path.name)
            continue
        extractor(candidate.meeting, candidate.path)
        if already_ingested(candidate.meeting.meeting_id, vault):
            result.ingested.append(candidate.path.name)
        else:
            result.failed.append(candidate.path.name)

    if not dry_run:
        _append_ledger_line(ledger, result)
    return result


def default_ledger():
    """Outside the vault deliberately: a no-op tick must leave the vault
    byte-identical so the auto-push loop makes no commit."""
    return pathlib.Path(os.environ.get(
        "MEM0_LEDGER",
        pathlib.Path.home() / "Library" / "Logs" / "mem0-meeting-ingest.log",
    )).expanduser()


def _append_ledger_line(ledger, result):
    ledger = pathlib.Path(ledger) if ledger is not None else default_ledger()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    line = (f"{stamp} ingested={len(result.ingested)} "
            f"skipped={len(result.skipped)}")
    if result.skipped:
        reasons = "; ".join(r.replace("\n", " ") for r in result.skipped)
        line += f" ({reasons})"
    line += f" already-present={result.already_present}"
    if result.failed:
        line += f" failed={len(result.failed)} ({', '.join(result.failed)})"
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def claude_extractor(meeting, path):
    ingest.run_extractor(meeting, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source_dir")
    ap.add_argument("--window-days", type=int, default=7)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    result = run_batch(args.source_dir, ingest.VAULT, claude_extractor,
                       window_days=args.window_days, dry_run=args.dry_run)

    if args.dry_run:
        for name in result.would_ingest:
            print(f"would ingest {name}")
        for reason in result.skipped:
            print(f"would skip {reason}")
        print(f"dry-run: {len(result.would_ingest)} to ingest, "
              f"{len(result.skipped)} skipped, "
              f"{result.already_present} already present")
    else:
        print(f"ingested={len(result.ingested)} skipped={len(result.skipped)} "
              f"already-present={result.already_present} "
              f"failed={len(result.failed)}")
    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
