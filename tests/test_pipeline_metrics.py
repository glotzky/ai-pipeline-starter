"""Integration tests: the real pipeline/run.py runs end to end against a fake claude, gh and Devin
in a scratch git repository, and we inspect the metrics it records."""
import json
import unittest

from helpers import SESSION_LINK, Sandbox, assert_valid, git, summarize

IDEA = "Add a thing\nSome private idea text that must not be recorded."
FAKE_KEY = "FAKE-test-secret-value-123456"  # a made-up value; scrubbing matches the exact env value


class PipelineMetricsTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)

    def assert_no_secrets(self, record):
        raw = json.dumps(record)
        for leaked in (SESSION_LINK, "SECRET-SESSION-LINK", "private idea text", FAKE_KEY, "review text"):
            self.assertNotIn(leaked, raw)

    def test_full_run_records_everything_and_is_pushed_to_the_branch(self):
        devin = self.sb.devin(acus=2.5)
        code, err = self.sb.run(IDEA, env={"ANTHROPIC_API_KEY": FAKE_KEY}, devin=devin)
        self.assertEqual((code, err), (0, None))
        r = self.sb.record()
        assert_valid(self, r)
        self.assertEqual((r["kind"], r["status"], r["stop_reason"], r["until"]), ("run", "success", "completed", "review"))
        self.assertEqual([s["name"] for s in r["stages"]],
                         ["researcher", "planner", "developer", "install", "tester", "reviewer", "pull_request"])
        self.assertTrue(all(s["status"] == "ok" and s["duration_seconds"] is not None for s in r["stages"]))
        self.assertEqual(r["retries"], {"developer_attempts": 1, "retries": 0, "reasons": []})
        self.assertEqual((r["tests"]["result"], r["tests"]["attempts"], r["tests"]["gate_failed"]), ("PASS", 1, False))
        self.assertEqual(r["review"]["verdict"], "SHIP")
        self.assertEqual((r["pull_request"]["created"], r["pull_request"]["number"]), (True, 7))
        self.assertEqual((r["devin"]["sessions"], r["devin"]["acus_consumed"]), (1, 2.5))
        t = r["ai_usage"]["totals"]
        self.assertEqual((t["calls"], t["calls_with_cost"], t["cost_complete"]), (4, 4, True))
        self.assertAlmostEqual(t["cost_usd"], 0.04, places=6)
        self.assertEqual((t["input_tokens"], t["output_tokens"]), (40, 20))
        self.assertEqual(r["github"], {"workflow_run_id": "12345", "run_attempt": 1})
        self.assertIsNotNone(r["ended_at"])
        self.assert_no_secrets(r)
        # the FINAL record is what was pushed to the run's branch (so it merges with the PR)
        self.assertEqual(self.sb.branch_record(r)["status"], "success")
        calls = self.sb.gh_calls()
        self.assertTrue(any(c.startswith("gh pr create --draft") for c in calls))
        self.assertTrue(calls[-1].startswith("gh workflow run ci.yml --ref pipeline/"))

    def test_existing_behaviour_unchanged_draft_pr_branch_naming_and_no_merge(self):
        self.sb.run(IDEA)
        r = self.sb.record()
        self.assertEqual(r["branch"], f"pipeline/{r['run_id']}")
        create = [c for c in self.sb.gh_calls() if c.startswith("gh pr create")][0]
        self.assertIn("--draft", create)
        self.assertIn("[pipeline SHIP] Add a thing", create)
        self.assertFalse(any("pr merge" in c for c in self.sb.gh_calls()))  # humans merge, never the pipeline

    def test_plan_only_run_is_stopped_not_failed_and_tests_not_run(self):
        code, _ = self.sb.run(IDEA, "--until", "plan")
        self.assertEqual(code, 0)
        r = self.sb.record()
        assert_valid(self, r)
        self.assertEqual((r["status"], r["stop_reason"]), ("stopped", "until_plan"))
        self.assertEqual([s["name"] for s in r["stages"]], ["researcher", "planner"])
        self.assertEqual(r["tests"]["result"], "not_run")
        self.assertEqual(r["review"]["verdict"], "not_run")
        self.assertFalse(r["pull_request"]["created"])
        self.assertEqual(r["devin"]["sessions"], 0)

    def test_blocked_planner_is_recorded_with_its_reason(self):
        code, _ = self.sb.run(IDEA, env={"FAKE_PLAN": "blocked"})
        self.assertEqual(code, 0)
        r = self.sb.record()
        self.assertEqual((r["status"], r["stop_reason"]), ("stopped", "planner_blocked"))

    def test_devin_pushing_nothing_is_a_failure_with_a_reason(self):
        code, _ = self.sb.run(IDEA, devin=self.sb.devin(push=False))
        self.assertEqual(code, 1)
        r = self.sb.record()
        assert_valid(self, r)
        self.assertEqual((r["status"], r["stop_reason"]), ("failure", "devin_no_commits"))
        self.assertEqual(r["devin"]["sessions"], 1)
        self.assertFalse(r["pull_request"]["created"])

    def test_failed_tests_trigger_a_counted_retry(self):
        devin = self.sb.devin()
        code, _ = self.sb.run(IDEA, env={"FAKE_TEST_FAILS": "1"}, devin=devin)
        self.assertEqual(code, 0)
        r = self.sb.record()
        self.assertEqual(len(devin.calls), 2)
        self.assertEqual(r["retries"], {"developer_attempts": 2, "retries": 1, "reasons": ["tests_failed"]})
        self.assertEqual((r["tests"]["result"], r["tests"]["attempts"]), ("PASS", 2))
        attempts = [(s["name"], s["attempt"]) for s in r["stages"] if s["name"] in ("developer", "tester")]
        self.assertEqual(attempts, [("developer", 1), ("tester", 1), ("developer", 2), ("tester", 2)])
        self.assertEqual(r["devin"]["acus_consumed"], 5.0)

    def test_missing_unit_tests_gate_is_recorded_and_still_works(self):
        devin = self.sb.devin(tests_from_attempt=2)  # first attempt ships source with no tests
        code, _ = self.sb.run(IDEA, devin=devin)
        self.assertEqual(code, 0)
        r = self.sb.record()
        self.assertTrue(r["tests"]["gate_failed"])
        self.assertEqual(r["retries"]["reasons"], ["tests_failed"])
        self.assertEqual(r["tests"]["result"], "PASS")

    def test_needs_work_review_is_a_counted_retry(self):
        code, _ = self.sb.run(IDEA, "--max-retries", "1", env={"FAKE_VERDICT": "VERDICT: NEEDS WORK"})
        self.assertEqual(code, 0)
        r = self.sb.record()
        self.assertEqual(r["retries"]["reasons"], ["needs_work"])
        self.assertEqual(r["review"]["verdict"], "NEEDS WORK")
        self.assertIn("[pipeline NEEDS WORK]", [c for c in self.sb.gh_calls() if c.startswith("gh pr create")][0])

    def test_exception_is_a_failure_with_a_scrubbed_error(self):
        env = {"FAKE_CLAUDE_MODE": "fail", "ANTHROPIC_API_KEY": FAKE_KEY, "LEAK_ME": FAKE_KEY}
        code, err = self.sb.run(IDEA, env=env)
        self.assertEqual(code, "error")
        self.assertIsInstance(err, RuntimeError)
        r = self.sb.record()
        assert_valid(self, r)
        self.assertEqual((r["status"], r["stop_reason"]), ("failure", "exception"))
        self.assertEqual(r["error"]["type"], "RuntimeError")
        self.assertEqual(r["stages"][0]["status"], "error")
        self.assert_no_secrets(r)
        summary = (self.sb.tmp / "pipeline-summary.md").read_text()  # what gets posted to the issue
        self.assertNotIn(FAKE_KEY, summary)
        self.assertEqual(self.sb.branch_record(r)["status"], "failure")

    def test_killed_run_leaves_an_honest_incomplete_record(self):
        code, err = self.sb.run(IDEA, devin=self.sb.devin(raises=KeyboardInterrupt()))
        self.assertEqual(code, "error")
        r = self.sb.record()
        assert_valid(self, r)
        self.assertEqual(r["status"], "incomplete")
        self.assertIsNone(r["ended_at"])
        self.assertIsNone(r["duration_seconds"])
        dev = [s for s in r["stages"] if s["name"] == "developer"][0]
        self.assertEqual(dev["status"], "error")
        self.assertEqual([s["name"] for s in r["stages"]][:2], ["researcher", "planner"])

    def test_plain_text_claude_output_still_works_and_records_no_usage(self):
        code, _ = self.sb.run(IDEA, env={"FAKE_CLAUDE_MODE": "text"})
        self.assertEqual(code, 0)  # behaviour identical to before the metrics were added
        r = self.sb.record()
        assert_valid(self, r)
        t = r["ai_usage"]["totals"]
        self.assertEqual((t["calls"], t["calls_with_cost"], t["cost_complete"]), (4, 0, False))
        self.assertIsNone(t["cost_usd"])
        self.assertIsNone(t["input_tokens"])
        self.assertIsNone(r["ai_usage"]["cost_source"])
        self.assertEqual(r["review"]["verdict"], "SHIP")

    def test_tokens_without_cost_do_not_fabricate_a_cost(self):
        code, _ = self.sb.run(IDEA, env={"FAKE_CLAUDE_MODE": "json_nocost"})
        self.assertEqual(code, 0)
        t = self.sb.record()["ai_usage"]["totals"]
        self.assertIsNone(t["cost_usd"])
        self.assertEqual(t["input_tokens"], 40)
        self.assertFalse(t["cost_complete"])

    def test_missing_acus_stay_null(self):
        code, _ = self.sb.run(IDEA, devin=self.sb.devin(acus=None))
        self.assertEqual(code, 0)
        d = self.sb.record()["devin"]
        self.assertEqual((d["sessions"], d["sessions_with_acus"]), (1, 0))
        self.assertIsNone(d["acus_consumed"])

    def test_fix_run_writes_its_own_record_and_updates_the_pr(self):
        self.sb.run(IDEA)
        first = self.sb.record()
        git("checkout", "-q", "main", cwd=self.sb.project)
        git("branch", "-D", first["branch"], cwd=self.sb.project)
        code, _ = self.sb.run("Make it red", "--fix-branch", first["branch"], devin=self.sb.devin())
        self.assertEqual(code, 0)
        self.assertEqual(len(self.sb.records()), 2)
        fix = [json.loads(p.read_text()) for p in self.sb.records() if p.name.endswith("-fix.json")][0]
        assert_valid(self, fix)
        self.assertEqual((fix["kind"], fix["status"]), ("fix", "success"))
        self.assertEqual((fix["pull_request"]["created"], fix["pull_request"]["updated"]), (False, True))
        self.assertEqual([s["name"] for s in fix["stages"]][:1], ["developer"])  # no research or planning
        self.assertNotIn("Make it red", json.dumps(fix))

    def test_metrics_can_be_switched_off_without_changing_the_run(self):
        code, _ = self.sb.run(IDEA, env={"PIPELINE_METRICS": "0"})
        self.assertEqual(code, 0)
        self.assertEqual(self.sb.records(), [])
        self.assertTrue(any(c.startswith("gh pr create") for c in self.sb.gh_calls()))

    def test_summarizer_reads_what_the_pipeline_wrote(self):
        self.sb.run(IDEA)
        records, skipped = summarize.load_records([self.sb.project / "metrics" / "runs"])
        self.assertEqual(skipped, [])
        s = summarize.summarize(records)
        self.assertEqual(s["success_rate"]["value"], 1.0)
        self.assertEqual(s["test_pass_rate"]["value"], 1.0)
        self.assertAlmostEqual(s["average_cost_usd"]["value"], 0.04, places=4)


if __name__ == "__main__":
    unittest.main()
