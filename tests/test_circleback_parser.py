import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent
                       / "skills" / "meeting-ingest" / "scripts"))

from circleback_parser import ParseError, parse

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


class ParseValidTranscript(unittest.TestCase):
    def test_parses_metadata_and_segments(self):
        meeting = parse(FIXTURES / "valid.md")
        self.assertEqual(meeting.title, "Acme <> Mem0 Kickoff")
        self.assertEqual(meeting.meeting_id, "Ab3xYz9QwErTy12345678")
        self.assertEqual(meeting.date, "2026-07-15")
        self.assertEqual(meeting.source, "circleback")
        self.assertEqual(len(meeting.segments), 4)
        self.assertEqual(meeting.segments[0].timestamp, "00:02")
        self.assertEqual(meeting.segments[0].speaker, "Jane Doe")
        self.assertEqual(meeting.segments[0].text, "Good afternoon, everyone.")
        self.assertEqual(meeting.speakers, ["Jane Doe", "Raj Patel"])


class ParseFailsLoudly(unittest.TestCase):
    def test_zero_segments_raises(self):
        with self.assertRaisesRegex(ParseError, "zero speaker segments"):
            parse(FIXTURES / "zero-segments.md")

    def test_missing_header_raises(self):
        with self.assertRaisesRegex(ParseError, "meeting_id"):
            parse(FIXTURES / "no-header.md")


REAL_TRANSCRIPTS = pathlib.Path(
    os.environ.get(
        "MEM0_TRANSCRIPTS",
        pathlib.Path.home() / "Desktop" / "resources" / "granola-transcripts",
    )
)
_REAL_FILES = sorted(REAL_TRANSCRIPTS.glob("2026-06-0[234]-*.md")) \
    if REAL_TRANSCRIPTS.exists() else []


@unittest.skipUnless(_REAL_FILES, "real Circleback exports not on this machine")
class ParseRealExports(unittest.TestCase):
    def test_all_real_exports_parse(self):
        self.assertEqual(len(_REAL_FILES), 3)
        for path in _REAL_FILES:
            meeting = parse(path)
            self.assertEqual(meeting.source, "circleback")
            self.assertGreater(len(meeting.segments), 50, path.name)
            self.assertGreaterEqual(len(meeting.speakers), 2, path.name)


if __name__ == "__main__":
    unittest.main()
