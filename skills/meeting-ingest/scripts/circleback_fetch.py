"""Normalize Circleback MCP payloads into the on-disk transcript format.

The MCP returns segments as {speaker, text, timestamp:<seconds>}. This module
renders them into the single format `circleback_parser` accepts, so a fetched
meeting is indistinguishable from one that was always on disk.

Fetching itself is an MCP tool call, which only an agent can make. The agent
hands the payloads here; this module owns the format contract.
"""
import pathlib
import re

SOURCE = "circleback"


def slugify(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower())
    return slug.strip("-")


def _clock(seconds):
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def normalize(meeting, transcript):
    """Render one meeting + its segments as a transcript document."""
    date = meeting["createdAt"][:10]
    lines = [
        f"# {meeting['name']}",
        "",
        f"- date: {date}",
        f"- meeting_id: {meeting['id']}",
        f"- source: {SOURCE}",
        f"- segments: {len(transcript)}",
        "",
        "## Transcript",
        "",
    ]
    for seg in transcript:
        text = " ".join(seg["text"].split())
        lines.append(f"[{_clock(seg['timestamp'])}] **{seg['speaker']}:** {text}")
    return "\n".join(lines) + "\n"


def write_transcript(meeting, transcript, dest_dir):
    """Write a normalized transcript. Returns the path, or None if empty.

    An empty transcript means Circleback has not finished processing yet.
    Writing a partial file would let the ID filter mark it done forever, so
    nothing is written and the meeting is picked up on a later run.
    """
    if not transcript:
        return None
    dest_dir = pathlib.Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{meeting['createdAt'][:10]}-{slugify(meeting['name'])}.md"
    path.write_text(normalize(meeting, transcript), encoding="utf-8")
    return path
