#!/usr/bin/env python3
"""End-to-end smoke test for the scan pipeline.

`--fake` swaps the Anthropic client for a deterministic stub, so this exercises
discovery -> chunking -> passes -> merge -> report -> SQLite resume without a
network call or an API key. It is the one check that fails if the pipeline
breaks; the model-facing prompts are not, and cannot be, tested here.

Run with: pytest -q   (or: python3 tests/test_smoke.py)
"""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from readthrough.cli import main  # noqa: E402
from readthrough.discover import FileInfo  # noqa: E402
from readthrough.store import Store  # noqa: E402

SUBJECT = '''\
import os
import sqlite3


def lookup(conn, user_id):
    """Deliberately awful, so a lens has something to find."""
    q = "SELECT * FROM users WHERE id = '%s'" % user_id
    return conn.execute(q).fetchall()


def run(cmd):
    return os.system(cmd)
'''


class FakeScan(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.subject = Path(self.tmp.name) / "subject"
        (self.subject / "app").mkdir(parents=True)
        (self.subject / "app" / "db.py").write_text(SUBJECT)
        self.out = Path(self.tmp.name) / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def scan(self, *extra):
        return main(["scan", str(self.subject), "--fake", "--quiet",
                     "--out", str(self.out), *extra])

    def test_scan_writes_every_report(self):
        self.assertEqual(self.scan(), 0)
        for name in ("report.md", "findings.json", "coverage.json",
                     "findings.sarif", "scan.db"):
            self.assertTrue((self.out / name).exists(), f"missing {name}")

    def test_coverage_accounts_for_every_file(self):
        self.scan()
        cov = json.loads((self.out / "findings.json").read_text())["coverage"]
        self.assertEqual(cov["files_eligible"], 1)
        self.assertEqual(cov["files_scanned"], 1)
        self.assertEqual(cov["tasks_failed"], 0)
        self.assertEqual(cov["tasks_done"], cov["tasks_total"])

    def test_sarif_is_valid_json_with_a_run(self):
        self.scan()
        sarif = json.loads((self.out / "findings.sarif").read_text())
        self.assertIn("runs", sarif)
        self.assertTrue(sarif["runs"])

    def test_rerun_resumes_instead_of_repeating(self):
        self.scan()
        first = json.loads((self.out / "findings.json").read_text())
        self.scan()  # same content hashes -> every pass already cached
        second = json.loads((self.out / "findings.json").read_text())
        self.assertEqual(first["usage"]["input_tokens"],
                         second["usage"]["input_tokens"])

    def test_unknown_lens_is_rejected_before_spending_anything(self):
        self.assertEqual(self.scan("--lenses", "nonsense"), 2)

    def test_estimate_only_writes_no_reports(self):
        self.assertEqual(self.scan("--estimate-only"), 0)
        self.assertFalse((self.out / "findings.json").exists())


class StaleFindings(unittest.TestCase):
    """Fixing a defect must remove it from the next report.

    Resume keys tasks by file content hash, so an edited file gets fresh
    passes -- but the rows recorded against the old content stayed in the
    database and were reported as current. The failure was silent and
    inverted the tool's whole premise: fix a vulnerability, re-scan, get told
    it is still there at line numbers that have since moved.
    """

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "scan.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _upsert(self, sha):
        self.store.upsert_files([FileInfo(
            rel="a.yml", path=str(Path(self.tmp.name) / "a.yml"), sha256=sha,
            lang="yaml", loc=10, size=100, status="pending", note="")])

    def _record(self, sha, findings):
        self.store.record_task(
            key=f"{sha}:injection:0:0", rel="a.yml", sha256=sha, lens="injection",
            chunk_idx=0, repeat_idx=0, start_line=1, end_line=10, status="done",
            attempts=1, error=None, in_tokens=1, out_tokens=1, duration_ms=1,
            served_model="test-model", findings=findings)

    FINDING = [{"title": "Command injection", "explanation": "x" * 20,
                "category": "injection", "severity": "high",
                "confidence": "high", "start_line": 3, "end_line": 4}]

    def test_finding_against_superseded_content_is_not_reported(self):
        self._upsert("AAA")
        self._record("AAA", self.FINDING)
        self.assertEqual(len(self.store.raw_findings()), 1)

        self._upsert("BBB")  # the file was edited
        self.assertEqual(self.store.raw_findings(), [],
                         "a finding about content that no longer exists was reported")

    def test_superseded_passes_do_not_count_as_coverage(self):
        self._upsert("AAA")
        self._record("AAA", [])
        self.assertEqual(len(self.store.tasks()), 1)

        self._upsert("BBB")
        self.assertEqual(self.store.tasks(), [],
                         "an edited file still counted as scanned")

    def test_rescanning_the_new_content_reports_normally(self):
        self._upsert("AAA")
        self._record("AAA", self.FINDING)
        self._upsert("BBB")
        self._record("BBB", self.FINDING)
        rows = self.store.raw_findings()
        self.assertEqual(len(rows), 1, "expected exactly the new content's finding")
        self.assertEqual(rows[0]["sha256"], "BBB")


if __name__ == "__main__":
    unittest.main(verbosity=2)
