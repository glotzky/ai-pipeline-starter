import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import SCHEMA, TEMPLATE, assert_valid, summarize

sys.path.insert(0, str(TEMPLATE / "pipeline"))
from run_metrics import Recorder  # noqa: E402


def make(run_id, status, duration, attempts=1, retries=0, tests="not_run", cost=None, acus=None, kind="run",
         ended="2026-01-01T00:10:00Z"):
    """A schema-valid record built from the real Recorder, then adjusted."""
    d = copy.deepcopy(Recorder(Path(tempfile.mkdtemp()), run_id, kind, "review", f"pipeline/{run_id}").data)
    d["status"] = status
    d["stop_reason"] = None if status == "incomplete" else "x"
    d["duration_seconds"] = duration
    d["ended_at"] = None if status == "incomplete" else ended
    d["retries"] = {"developer_attempts": attempts, "retries": retries, "reasons": ["tests_failed"] * retries}
    d["tests"]["result"] = tests
    d["devin"]["acus_consumed"] = acus
    t = d["ai_usage"]["totals"]
    if cost is not None:
        t["cost_usd"], t["calls"], t["calls_with_cost"], t["cost_complete"] = cost, 1, 1, True
        d["ai_usage"]["cost_source"] = "claude_cli_reported"
    return d


def write_all(folder, records):
    folder = Path(folder)
    for i, r in enumerate(records):
        (folder / f"{r['run_id']}-{i}.json").write_text(json.dumps(r))


class SummarizeTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.records = [
            make("r1", "success", 600, 1, 0, "PASS", cost=0.10, acus=2.0),
            make("r2", "success", 1200, 3, 2, "PASS", cost=0.30, acus=6.0),
            make("r3", "failure", 300, 1, 0, "FAIL", cost=None, acus=None),
            make("r4", "stopped", 100, 0, 0, "not_run", cost=0.02),
            make("r5", "incomplete", None, 1, 0, "not_run"),
        ]
        for r in self.records:
            assert_valid(self, r)
        write_all(self.dir, self.records)

    def summary(self, **kw):
        records, skipped = summarize.load_records([self.dir])
        return summarize.summarize(records, **kw), skipped

    def test_counts_and_success_rate_exclude_stopped_and_incomplete(self):
        s, _ = self.summary()
        self.assertEqual(s["runs"], 5)
        self.assertEqual(s["by_status"], {"success": 2, "failure": 1, "stopped": 1, "incomplete": 1})
        self.assertAlmostEqual(s["success_rate"]["value"], 2 / 3, places=3)
        self.assertEqual(s["success_rate"]["based_on"], 3)

    def test_median_duration_ignores_incomplete_runs(self):
        s, _ = self.summary()
        self.assertEqual(s["median_duration_seconds"], {"value": 450.0, "based_on": 4})

    def test_average_retries_only_counts_runs_that_reached_the_developer(self):
        s, _ = self.summary()
        self.assertEqual(s["average_developer_retries"], {"value": 0.5, "based_on": 4})

    def test_test_pass_rate_only_counts_runs_that_ran_tests(self):
        s, _ = self.summary()
        self.assertAlmostEqual(s["test_pass_rate"]["value"], 2 / 3, places=3)
        self.assertEqual(s["test_pass_rate"]["based_on"], 3)

    def test_average_cost_uses_only_runs_with_reported_cost(self):
        s, _ = self.summary()
        self.assertAlmostEqual(s["average_cost_usd"]["value"], 0.14, places=4)
        self.assertEqual(s["average_cost_usd"]["based_on"], 3)

    def test_average_devin_acus_ignores_missing(self):
        s, _ = self.summary()
        self.assertEqual(s["average_devin_acus"], {"value": 4.0, "based_on": 2})

    def test_no_data_is_none_never_zero(self):
        records = [make("a", "incomplete", None, 0, 0, "not_run")]
        s = summarize.summarize(records)
        for key in ("success_rate", "median_duration_seconds", "average_developer_retries",
                    "test_pass_rate", "average_cost_usd", "average_devin_acus"):
            self.assertIsNone(s[key]["value"], key)
            self.assertEqual(s[key]["based_on"], 0, key)

    def test_empty_folder(self):
        empty = Path(tempfile.mkdtemp())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(summarize.main([str(empty)]), 0)
        self.assertIn("No run records found", out.getvalue())

    def test_invalid_and_unreadable_files_are_skipped_and_reported(self):
        (self.dir / "bad.json").write_text('{"run_id": "x"}')
        (self.dir / "junk.json").write_text("not json at all")
        s, skipped = self.summary()
        self.assertEqual(s["runs"], 5)
        self.assertEqual(len(skipped), 2)

    def test_duplicate_run_prefers_finished_over_incomplete(self):
        partial = make("dup", "incomplete", None, 1)
        final = make("dup", "success", 50, 1, 0, "PASS")
        folder = Path(tempfile.mkdtemp())
        (folder / "a.json").write_text(json.dumps(partial))
        (folder / "b.json").write_text(json.dumps(final))
        records, _ = summarize.load_records([folder])
        self.assertEqual([r["status"] for r in records], ["success"])
        (folder / "a.json").write_text(json.dumps(final))  # same result regardless of file order
        (folder / "b.json").write_text(json.dumps(partial))
        records, _ = summarize.load_records([folder])
        self.assertEqual([r["status"] for r in records], ["success"])

    def test_kind_filter_and_fix_records_do_not_collide_with_runs(self):
        folder = Path(tempfile.mkdtemp())
        write_all(folder, [make("same", "success", 10, kind="run"), make("same", "success", 20, kind="fix")])
        records, _ = summarize.load_records([folder])
        self.assertEqual(len(records), 2)
        self.assertEqual(summarize.summarize(records, kind="fix")["runs"], 1)

    def test_cli_json_output_and_text_output(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            summarize.main([str(self.dir), "--json"])
        self.assertEqual(json.loads(out.getvalue())["summary"]["runs"], 5)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            summarize.main([str(self.dir)])
        text = out.getvalue()
        self.assertIn("Success rate:", text)
        self.assertIn("66.7%", text)
        self.assertIn("[n=3]", text)

    def test_text_output_says_n_a_when_no_cost_data(self):
        folder = Path(tempfile.mkdtemp())
        write_all(folder, [make("x", "success", 10, 1, 0, "PASS")])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            summarize.main([str(folder)])
        self.assertIn("n/a (no data)", out.getvalue())

    def test_default_path_is_the_metrics_runs_folder(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(summarize.main([]), 0)


if __name__ == "__main__":
    unittest.main()
