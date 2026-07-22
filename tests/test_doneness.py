"""Doneness must mean 'a summary note exists', not 'the id appears somewhere'.

The extractor copies the transcript into Meetings/transcripts/ as its FIRST
action, and normalized transcripts carry `- meeting_id: <id>` in their header.
A recursive substring search over Meetings/ therefore reports a meeting as
done the instant copying finishes — before any summary is written. If the
extractor then dies, the identity filter excludes that meeting forever and it
is lost with no note and no error.
"""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent
                       / "skills" / "meeting-ingest" / "scripts"))

from ingest import already_ingested

MEETING_ID = "kQMUKO0I26rmCttWv66Nm"


def _vault(tmp):
    v = pathlib.Path(tmp)
    (v / "Meetings" / "transcripts").mkdir(parents=True)
    return v


class Doneness(unittest.TestCase):
    def test_transcript_copy_alone_is_not_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = _vault(tmp)
            (v / "Meetings" / "transcripts" / "m.transcript.md").write_text(
                f"# M\n\n- date: 2026-06-02\n- meeting_id: {MEETING_ID}\n"
                "- source: circleback\n", encoding="utf-8")
            self.assertIsNone(already_ingested(MEETING_ID, v))

    def test_summary_with_meeting_id_frontmatter_is_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = _vault(tmp)
            (v / "Meetings" / "m-summary.md").write_text(
                f'---\ntitle: "Summary: M"\nmeeting-id: "{MEETING_ID}"\n---\n\n# M\n',
                encoding="utf-8")
            self.assertEqual(already_ingested(MEETING_ID, v), "m-summary.md")

    def test_id_mentioned_in_prose_is_not_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = _vault(tmp)
            (v / "Meetings" / "other-summary.md").write_text(
                f'---\ntitle: "Other"\nmeeting-id: "SomeOtherId000000000"\n---\n\n'
                f"# Other\n\nRelated to meeting {MEETING_ID} discussed earlier.\n",
                encoding="utf-8")
            self.assertIsNone(already_ingested(MEETING_ID, v))

    def test_missing_meetings_dir_is_not_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(already_ingested(MEETING_ID, pathlib.Path(tmp)))


if __name__ == "__main__":
    unittest.main()
