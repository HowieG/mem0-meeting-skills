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
        # Past an hour it must roll into HH:MM:SS, not run the minutes field
        # to three digits — the parser cannot match [62:05]'s longer cousins.
        self.assertIn("[01:02:05] **Manmeet Sethi:** Doing well.", text)

    def test_long_meeting_keeps_every_segment(self):
        """A two-hour call must not lose the dialogue past 100 minutes.

        Unbounded minutes rendered `[100:05]`, which the parser's \\d{2}:\\d{2}
        anchor could not match. Enough segments survived that the zero-segment
        guard never fired, so a long customer call ingested silently truncated.
        """
        long_transcript = [
            {"speaker": "A", "text": "opening", "timestamp": 10},
            {"speaker": "B", "text": "past one hundred minutes", "timestamp": 100 * 60 + 5},
            {"speaker": "A", "text": "past two hours", "timestamp": 2 * 3600 + 30},
        ]
        with tempfile.TemporaryDirectory() as d:
            path = write_transcript(MEETING, long_transcript, pathlib.Path(d))
            meeting = parse(path)
            self.assertEqual(len(meeting.segments), 3)
            self.assertEqual(meeting.segments[-1].text, "past two hours")

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
            self.assertEqual(path.name, "2026-06-01-t-mobile-mem0-NaKjbI7V.md")

    def test_same_title_and_date_do_not_collide(self):
        """Two meetings sharing a title and date must not share a filename.

        Recurring calendar invites produce exactly this: "30 Min Meeting
        between X and Y" twice in one day. Slugging on title+date alone made
        the second write clobber the first, destroying a transcript before it
        was ever ingested — and the id filter cannot notice a file that no
        longer exists.
        """
        a = {"id": "kQMUKO0I26rmCttWv66Nm", "name": "30 Min Meeting",
             "createdAt": "2026-06-02T17:31:18.829Z"}
        b = {"id": "bdRQMdrfVazWp69uO6bMG", "name": "30 Min Meeting",
             "createdAt": "2026-06-02T16:30:08.346Z"}
        with tempfile.TemporaryDirectory() as d:
            pa = write_transcript(a, TRANSCRIPT, pathlib.Path(d))
            pb = write_transcript(b, TRANSCRIPT, pathlib.Path(d))
            self.assertNotEqual(pa, pb)
            self.assertEqual(len(list(pathlib.Path(d).iterdir())), 2)
            self.assertEqual(parse(pa).meeting_id, a["id"])
            self.assertEqual(parse(pb).meeting_id, b["id"])

    def test_rewriting_the_same_meeting_is_stable(self):
        with tempfile.TemporaryDirectory() as d:
            first = write_transcript(MEETING, TRANSCRIPT, pathlib.Path(d))
            again = write_transcript(MEETING, TRANSCRIPT, pathlib.Path(d))
            self.assertEqual(first, again)
            self.assertEqual(len(list(pathlib.Path(d).iterdir())), 1)

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
