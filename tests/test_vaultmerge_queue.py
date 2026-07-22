import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).parent.parent \
    / "skills" / "granola-to-obsidian-howard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vaultmerge as vm

MTG = "2026-07-01-acme-demo-summary"
MDATE = "2026-07-01"


def seed_gappy_vault(vault):
    """Four notes with gaps plus one fully-clean person.

    Every entity is in exactly ONE meeting — audit()'s stale-stub check
    deliberately ignores these, which is why queue() exists.
    """
    (vault / "Meetings").mkdir(parents=True, exist_ok=True)
    (vault / "Meetings" / f"{MTG}.md").write_text(
        f'---\ntitle: "{MTG}"\ndate: {MDATE}\ntags: [meeting]\n---\n\n# Acme demo\n',
        encoding="utf-8")
    vm.person("Younes", MTG, MDATE, company="Mem0", role="Sales FTE",
              notes=["**Jul 1:** ran the CBRE demo."])          # unconfirmed only
    vm.person("Disha", MTG, MDATE, status="confirmed", role="Engineer",
              notes=["**Jul 1:** asked about eval harness."])   # company Unknown
    vm.person("Parush", MTG, MDATE, company="Acme",
              notes=["**Jul 1:** owns the pilot budget."])      # unconfirmed + role Unknown
    (vault / "Companies").mkdir(parents=True, exist_ok=True)
    (vault / "Companies" / "Nessie Labs.md").write_text(
        '---\ntitle: "Nessie Labs"\ndate: 2026-07-01\ntags: [company]\n'
        'aliases: []\ntype: company\nstatus: active\ncompany: ""\nrole: "Unknown"\n'
        f'related:\n  - "{MTG}"\n---\n\n# Nessie Labs\n\n'
        "## Notes\n- **Jul 1:** garbled competitor mention.\n",
        encoding="utf-8")
    vm.person("Howard Gil", MTG, MDATE, status="confirmed",
              company="Mem0", role="CTO",
              notes=["**Jul 1:** framed the pilot."])           # fully clean


class QueueTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_vault = vm.VAULT
        vm.VAULT = pathlib.Path(self._tmp.name)
        vm.CONFLICTS.clear()

    def tearDown(self):
        vm.VAULT = self._old_vault
        vm.CONFLICTS.clear()
        self._tmp.cleanup()


class QueueFindsEveryGap(QueueTestCase):
    def setUp(self):
        super().setUp()
        seed_gappy_vault(vm.VAULT)
        self.gaps = {g["name"]: g for g in vm.queue()}

    def test_exactly_the_four_gappy_notes(self):
        self.assertEqual(sorted(self.gaps),
                         ["Disha", "Nessie Labs", "Parush", "Younes"])

    def test_unconfirmed_with_known_fields(self):
        g = self.gaps["Younes"]
        self.assertEqual(g["kind"], ["unconfirmed-status"])
        self.assertEqual(g["fields"], [])
        self.assertEqual(g["evidence"], ["**Jul 1:** ran the CBRE demo."])
        self.assertEqual(pathlib.Path(g["path"]),
                         vm.VAULT / "People" / "Younes.md")

    def test_confirmed_but_company_unknown(self):
        g = self.gaps["Disha"]
        self.assertEqual(g["kind"], ["unknown-field"])
        self.assertEqual(g["fields"], ["company"])
        self.assertEqual(g["evidence"], ["**Jul 1:** asked about eval harness."])

    def test_unconfirmed_and_unknown_merge_into_one_entry(self):
        g = self.gaps["Parush"]
        self.assertEqual(g["kind"], ["unconfirmed-status", "unknown-field"])
        self.assertEqual(g["fields"], ["role"])

    def test_company_note_with_unknown_and_empty_fields(self):
        g = self.gaps["Nessie Labs"]
        self.assertEqual(g["kind"], ["unknown-field"])
        self.assertEqual(g["fields"], ["company", "role"])
        self.assertEqual(g["evidence"], ["**Jul 1:** garbled competitor mention."])
        self.assertEqual(pathlib.Path(g["path"]),
                         vm.VAULT / "Companies" / "Nessie Labs.md")

    def test_single_meeting_entities_appear_even_though_audit_ignores_them(self):
        self.assertEqual(vm.audit()["stale_stubs"], [])
        self.assertEqual(len(self.gaps), 4)


class QueueOnCleanVault(QueueTestCase):
    def test_empty(self):
        vm.person("Howard Gil", MTG, MDATE, status="confirmed",
                  company="Mem0", role="CTO", notes=["**Jul 1:** clean."])
        self.assertEqual(vm.queue(), [])


def run_cli(vault, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "vaultmerge.py"), *args],
        capture_output=True, text=True,
        env={**os.environ, "MEM0_VAULT": str(vault)})


class QueueCli(QueueTestCase):
    def test_exit_3_when_gaps_exist(self):
        seed_gappy_vault(vm.VAULT)
        r = run_cli(vm.VAULT, "--queue")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        for name in ("Younes", "Disha", "Parush", "Nessie Labs"):
            self.assertIn(name, r.stdout)
        self.assertNotIn("QUEUE EMPTY", r.stdout)

    def test_exit_0_and_queue_empty_when_clean(self):
        vm.person("Howard Gil", MTG, MDATE, status="confirmed",
                  company="Mem0", role="CTO", notes=["**Jul 1:** clean."])
        r = run_cli(vm.VAULT, "--queue")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("QUEUE EMPTY", r.stdout)

    def test_no_arg_audit_behavior_unchanged(self):
        seed_gappy_vault(vm.VAULT)
        r = run_cli(vm.VAULT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        self.assertTrue(lines[0].startswith("counts:"), r.stdout)
        self.assertEqual(lines[-1], "CLEAN")
        self.assertNotIn("QUEUE", r.stdout)


if __name__ == "__main__":
    unittest.main()
