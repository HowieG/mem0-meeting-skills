import datetime
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent
                       / "skills" / "meeting-ingest" / "scripts"))

from batch import filter_new, find_candidates, run_batch

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


def write_meeting_note(vault, meeting_id):
    notes = pathlib.Path(vault) / "Meetings"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / f"{meeting_id}.md").write_text(
        f'---\nmeeting-id: "{meeting_id}"\n---\n', encoding="utf-8")


class FilterNew(TempDirTestCase):
    def setUp(self):
        self.source = self.make_dir()
        self.vault = self.make_dir()

    def candidates(self):
        return find_candidates(self.source, window_days=7, today=TODAY)

    def test_returns_exactly_the_not_yet_ingested(self):
        write_transcript(self.source, "a.md", "MeetingAaaa0000000001", "2026-07-19")
        write_transcript(self.source, "b.md", "MeetingBbbb0000000001", "2026-07-20")
        write_meeting_note(self.vault, "MeetingAaaa0000000001")

        new = filter_new(self.candidates(), self.vault)

        self.assertEqual([c.path.name for c in new], ["b.md"])

    def test_empty_once_all_notes_exist(self):
        write_transcript(self.source, "a.md", "MeetingAaaa0000000001", "2026-07-19")
        write_transcript(self.source, "b.md", "MeetingBbbb0000000001", "2026-07-20")
        write_meeting_note(self.vault, "MeetingAaaa0000000001")
        write_meeting_note(self.vault, "MeetingBbbb0000000001")

        self.assertEqual(filter_new(self.candidates(), self.vault), [])

    def test_id_anywhere_under_meetings_counts_as_done(self):
        write_transcript(self.source, "a.md", "MeetingAaaa0000000001", "2026-07-19")
        nested = pathlib.Path(self.vault) / "Meetings" / "transcripts"
        nested.mkdir(parents=True)
        (nested / "copy.md").write_text(
            "- meeting_id: MeetingAaaa0000000001\n", encoding="utf-8")

        self.assertEqual(filter_new(self.candidates(), self.vault), [])

    def test_error_candidates_pass_through(self):
        (self.source / "summary.md").write_text(
            "# Weekly Summary\n\nNo header.\n", encoding="utf-8")

        new = filter_new(self.candidates(), self.vault)

        self.assertEqual([c.path.name for c in new], ["summary.md"])


def note_writing_extractor(vault):
    def extract(meeting, path):
        write_meeting_note(vault, meeting.meeting_id)
    return extract


def vault_snapshot(vault):
    root = pathlib.Path(vault)
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


class RunBatch(TempDirTestCase):
    def setUp(self):
        self.source = self.make_dir()
        self.vault = self.make_dir()
        self.ledger = self.make_dir() / "logs" / "ingest.log"

    def run_it(self, extractor=None, **kwargs):
        extractor = extractor or note_writing_extractor(self.vault)
        return run_batch(self.source, self.vault, extractor,
                         today=TODAY, ledger=self.ledger, **kwargs)

    def test_ingests_new_and_reports_already_present(self):
        write_transcript(self.source, "a.md", "MeetingAaaa0000000001", "2026-07-19")
        write_transcript(self.source, "b.md", "MeetingBbbb0000000001", "2026-07-20")
        write_transcript(self.source, "c.md", "MeetingCccc0000000001", "2026-07-21")
        write_meeting_note(self.vault, "MeetingCccc0000000001")

        result = self.run_it()

        self.assertEqual(sorted(result.ingested), ["a.md", "b.md"])
        self.assertEqual(result.already_present, 1)
        self.assertEqual(result.skipped, [])
        self.assertEqual(result.failed, [])

    def test_second_run_is_a_no_op_and_vault_is_byte_identical(self):
        write_transcript(self.source, "a.md", "MeetingAaaa0000000001", "2026-07-19")
        write_transcript(self.source, "b.md", "MeetingBbbb0000000001", "2026-07-20")
        write_transcript(self.source, "c.md", "MeetingCccc0000000001", "2026-07-21")
        write_meeting_note(self.vault, "MeetingCccc0000000001")

        self.run_it()
        before = vault_snapshot(self.vault)
        result = self.run_it()

        self.assertEqual(result.ingested, [])
        self.assertEqual(result.already_present, 3)
        self.assertEqual(vault_snapshot(self.vault), before)

    def test_thin_transcript_skipped_and_nothing_written(self):
        write_transcript(self.source, "thin.md", "ThinMeeting0000000001",
                         "2026-07-20", lines=["hello there", "not much said"])

        result = self.run_it()

        self.assertEqual(result.ingested, [])
        self.assertEqual(len(result.skipped), 1)
        self.assertIn("thin.md", result.skipped[0])
        self.assertEqual(vault_snapshot(self.vault), {})

    def test_unparseable_file_skipped_with_reason(self):
        (self.source / "summary.md").write_text(
            "# Weekly Summary\n\nNo header.\n", encoding="utf-8")

        result = self.run_it()

        self.assertEqual(result.ingested, [])
        self.assertEqual(len(result.skipped), 1)
        self.assertIn("summary.md", result.skipped[0])
        self.assertEqual(vault_snapshot(self.vault), {})

    def test_extractor_that_records_nothing_counts_as_failed(self):
        write_transcript(self.source, "a.md", "MeetingAaaa0000000001", "2026-07-19")

        result = self.run_it(extractor=lambda meeting, path: None)

        self.assertEqual(result.ingested, [])
        self.assertEqual(result.failed, ["a.md"])

    def test_dry_run_calls_no_extractor_and_writes_nothing(self):
        write_transcript(self.source, "a.md", "MeetingAaaa0000000001", "2026-07-19")
        calls = []

        result = self.run_it(
            extractor=lambda meeting, path: calls.append(path), dry_run=True)

        self.assertEqual(calls, [])
        self.assertEqual(result.would_ingest, ["a.md"])
        self.assertEqual(vault_snapshot(self.vault), {})


class Ledger(TempDirTestCase):
    def setUp(self):
        self.source = self.make_dir()
        self.vault = self.make_dir()
        self.ledger = self.make_dir() / "logs" / "ingest.log"

    def run_it(self, **kwargs):
        return run_batch(self.source, self.vault,
                         note_writing_extractor(self.vault),
                         today=TODAY, ledger=self.ledger, **kwargs)

    def lines(self):
        return self.ledger.read_text(encoding="utf-8").splitlines()

    def test_exactly_one_line_per_run(self):
        write_transcript(self.source, "a.md", "MeetingAaaa0000000001", "2026-07-19")

        self.run_it()
        self.assertEqual(len(self.lines()), 1)
        self.run_it()
        self.assertEqual(len(self.lines()), 2)

    def test_line_carries_counts_and_skip_reasons(self):
        write_transcript(self.source, "a.md", "MeetingAaaa0000000001", "2026-07-19")
        write_transcript(self.source, "thin.md", "ThinMeeting0000000001",
                         "2026-07-20", lines=["barely a word"])
        write_transcript(self.source, "c.md", "MeetingCccc0000000001", "2026-07-21")
        write_meeting_note(self.vault, "MeetingCccc0000000001")

        self.run_it()

        (line,) = self.lines()
        self.assertIn("ingested=1", line)
        self.assertIn("skipped=1", line)
        self.assertIn("thin.md", line)
        self.assertIn("thin transcript", line)
        self.assertIn("already-present=1", line)

    def test_thin_skip_is_not_recorded_as_a_success(self):
        write_transcript(self.source, "thin.md", "ThinMeeting0000000001",
                         "2026-07-20", lines=["barely a word"])

        self.run_it()

        (line,) = self.lines()
        self.assertIn("ingested=0", line)
        self.assertIn("skipped=1", line)
        self.assertIn("thin.md", line)

    def test_ledger_path_defaults_to_env(self):
        env_ledger = self.make_dir() / "nested" / "env.log"
        os.environ["MEM0_LEDGER"] = str(env_ledger)
        self.addCleanup(os.environ.pop, "MEM0_LEDGER", None)
        write_transcript(self.source, "a.md", "MeetingAaaa0000000001", "2026-07-19")

        run_batch(self.source, self.vault,
                  note_writing_extractor(self.vault), today=TODAY)

        self.assertEqual(len(env_ledger.read_text(encoding="utf-8").splitlines()), 1)

    def test_dry_run_writes_no_ledger_line(self):
        write_transcript(self.source, "a.md", "MeetingAaaa0000000001", "2026-07-19")

        self.run_it(dry_run=True)

        self.assertFalse(self.ledger.exists())


if __name__ == "__main__":
    unittest.main()
