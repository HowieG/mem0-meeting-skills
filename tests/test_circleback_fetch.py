import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent
                       / "skills" / "meeting-ingest" / "scripts"))

from circleback_fetch import normalize, slugify, write_transcript
from circleback_parser import parse

MEETING = {
    "id": "NaKjbI7VDtKnuDqIrFQ2G",
    "name": "T-Mobile <> Mem0",
    "createdAt": "2026-06-01T18:01:25.660Z",
}
TRANSCRIPT = [
    {"speaker": "Manmeet Sethi", "text": "Hello, hey Joe.", "timestamp": 5.2},
    {"speaker": "joe", "text": "I'm good.", "timestamp": 67.6},
    {"speaker": "Manmeet Sethi", "text": "Doing well.", "timestamp": 3725.0},
]


class Normalize(unittest.TestCase):
    def test_produces_parseable_transcript(self):
        text = normalize(MEETING, TRANSCRIPT)
        self.assertIn("# T-Mobile <> Mem0", text)
        self.assertIn("- meeting_id: NaKjbI7VDtKnuDqIrFQ2G", text)
        self.assertIn("- date: 2026-06-01", text)
        self.assertIn("- source: circleback", text)
        self.assertIn("- segments: 3", text)
        self.assertIn("## Transcript", text)

    def test_timestamps_render_as_clock_time(self):
        text = normalize(MEETING, TRANSCRIPT)
        self.assertIn("[00:05] **Manmeet Sethi:** Hello, hey Joe.", text)
        self.assertIn("[01:07] **joe:** I'm good.", text)
        self.assertIn("[62:05] **Manmeet Sethi:** Doing well.", text)

    def test_round_trips_through_the_parser(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_transcript(MEETING, TRANSCRIPT, pathlib.Path(d))
            meeting = parse(path)
            self.assertEqual(meeting.meeting_id, "NaKjbI7VDtKnuDqIrFQ2G")
            self.assertEqual(meeting.date, "2026-06-01")
            self.assertEqual(len(meeting.segments), 3)
            self.assertEqual(meeting.speakers, ["Manmeet Sethi", "joe"])

    def test_filename_is_dated_and_slugged(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_transcript(MEETING, TRANSCRIPT, pathlib.Path(d))
            self.assertEqual(path.name, "2026-06-01-t-mobile-mem0.md")

    def test_empty_transcript_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_transcript(MEETING, [], pathlib.Path(d))
            self.assertIsNone(path)
            self.assertEqual(list(pathlib.Path(d).iterdir()), [])


class Slugify(unittest.TestCase):
    def test_strips_punctuation_and_lowercases(self):
        self.assertEqual(slugify("T-Mobile <> Mem0"), "t-mobile-mem0")
        self.assertEqual(slugify("30 Min Meeting: Manmeet & Sid"),
                         "30-min-meeting-manmeet-sid")


if __name__ == "__main__":
    unittest.main()
