#!/usr/bin/env python3
"""Idempotent batch ingest of normalized Circleback transcripts.

    python3 batch.py <source_dir> [--window-days N] [--dry-run]

Scans source_dir for transcripts dated within the window and ingests only
meetings whose meeting_id appears nowhere under vault/Meetings/. The vault
alone is authoritative — no watermarks, no timestamps, no state files.
"""
import datetime
import pathlib
import sys
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from circleback_parser import ParseError, parse
from ingest import already_ingested


@dataclass(frozen=True)
class Candidate:
    path: pathlib.Path
    meeting: object = None
    error: str = None


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
