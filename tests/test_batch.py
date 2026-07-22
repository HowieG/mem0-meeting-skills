import datetime
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent
                       / "skills" / "meeting-ingest" / "scripts"))

from batch import filter_new, find_candidates

TODAY = datetime.date(2026, 7, 21)

CHATTY_LINE = ("we agreed the rollout starts with the pilot group next month "
               "and SSO lands before phase two begins")


def write_transcript(directory, name, meeting_id, date, lines=None):
    lines = [CHATTY_LINE, CHATTY_LINE] if lines is None else lines
    segments = "\n".join(
        f"[00:{i:02d}] **Jane Doe:** {text}" for i, text in enumerate(lines))
    path = pathlib.Path(directory) / name
    path.write_text(
        f"# {name}\n\n"
        f"- date: {date}\n"
        f"- meeting_id: {meeting_id}\n"
        f"- source: circleback\n"
        f"- segments: {len(lines)}\n\n"
        f"## Transcript\n\n{segments}\n",
        encoding="utf-8")
    return path


class TempDirTestCase(unittest.TestCase):
    def make_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return pathlib.Path(tmp.name)


class FindCandidates(TempDirTestCase):
    def setUp(self):
        self.source = self.make_dir()

    def test_keeps_meetings_dated_within_window(self):
        write_transcript(self.source, "fresh.md", "FreshMeeting000000001", "2026-07-19")
        write_transcript(self.source, "stale.md", "StaleMeeting000000001", "2026-06-01")

        candidates = find_candidates(self.source, window_days=7, today=TODAY)

        self.assertEqual([c.path.name for c in candidates], ["fresh.md"])
        self.assertEqual(candidates[0].meeting.meeting_id, "FreshMeeting000000001")
        self.assertIsNone(candidates[0].error)

    def test_unparseable_files_are_error_candidates(self):
        (self.source / "summary.md").write_text(
            "# Weekly Summary\n\nNo header, no segments.\n", encoding="utf-8")
        write_transcript(self.source, "fresh.md", "FreshMeeting000000001", "2026-07-19")

        candidates = find_candidates(self.source, window_days=7, today=TODAY)

        by_name = {c.path.name: c for c in candidates}
        self.assertEqual(set(by_name), {"fresh.md", "summary.md"})
        self.assertIsNone(by_name["summary.md"].meeting)
        self.assertIn("summary.md", by_name["summary.md"].error)

    def test_unparseable_header_date_is_an_error_candidate(self):
        write_transcript(self.source, "odd-date.md", "OddDateMeeting0000001", "July 19th")

        candidates = find_candidates(self.source, window_days=7, today=TODAY)

        self.assertEqual(len(candidates), 1)
        self.assertIsNone(candidates[0].meeting)
        self.assertIn("date", candidates[0].error)


if __name__ == "__main__":
    unittest.main()
