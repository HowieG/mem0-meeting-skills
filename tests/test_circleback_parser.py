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


if __name__ == "__main__":
    unittest.main()
