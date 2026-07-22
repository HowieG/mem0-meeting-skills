"""Parser for normalized Circleback transcript exports.

The one format this pipeline accepts: a title line, a header block carrying
meeting_id, and speaker-labelled segments under `## Transcript`. Anything else
raises ParseError — an empty or partial parse is indistinguishable from
"no new meetings" downstream, so drift must fail here, loudly.
"""
import pathlib
import re
from dataclasses import dataclass

_SEGMENT = re.compile(r"^\[(\d{2}:\d{2}(?::\d{2})?)\] \*\*([^*]+?):\*\* ?(.*)$")
_HEADER_FIELD = re.compile(r"^- (date|meeting_id|source|segments): (.+)$")


class ParseError(Exception):
    """The file is not a well-formed Circleback transcript export."""


@dataclass(frozen=True)
class Segment:
    timestamp: str
    speaker: str
    text: str


@dataclass(frozen=True)
class Meeting:
    title: str
    meeting_id: str
    date: str
    source: str
    segments: tuple

    @property
    def speakers(self):
        seen = []
        for seg in self.segments:
            if seg.speaker not in seen:
                seen.append(seg.speaker)
        return seen


def parse(path):
    path = pathlib.Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    title = None
    fields = {}
    segments = []
    for line in lines:
        if title is None and line.startswith("# "):
            title = line[2:].strip()
            continue
        m = _HEADER_FIELD.match(line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
            continue
        m = _SEGMENT.match(line)
        if m:
            segments.append(Segment(m.group(1), m.group(2).strip(), m.group(3)))

    missing = [f for f in ("meeting_id", "date", "source") if f not in fields]
    if missing:
        raise ParseError(
            f"{path.name}: header missing {', '.join(missing)} — not a "
            "normalized Circleback export"
        )

    declared = fields.get("segments")
    if declared is not None and declared.isdigit() and int(declared) != len(segments):
        raise ParseError(
            f"{path.name}: header declares {declared} segments but {len(segments)} "
            "parsed — the export format drifted and dialogue is being dropped"
        )

    if not segments:
        raise ParseError(
            f"{path.name}: zero speaker segments — either the transcript is "
            "empty upstream or the export format drifted; refusing to return "
            "an empty parse"
        )

    return Meeting(
        title=title,
        meeting_id=fields["meeting_id"],
        date=fields["date"],
        source=fields["source"],
        segments=tuple(segments),
    )
