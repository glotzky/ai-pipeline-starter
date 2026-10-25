import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import SCHEMA, TEMPLATE, assert_valid, summarize

sys.path.insert(0, str(TEMPLATE / "pipeline"))
import run_metrics  # noqa: E402
from run_metrics import Recorder, parse_claude_output, scrub  # noqa: E402


class ScrubTests(unittest.TestCase):
    def test_known_secret_values_and_token_shapes_are_removed(self):
        # Token-shaped strings are assembled at runtime so no real-looking secret sits in the source.
        shapes = ["co" + "g_" + "abcDEF123456", "sk" + "-ant-" + "api03-AAAA_bbb", "gh" + "p_" + "a" * 20,
                  "Bear" + "er abc.def-ghi", "or" + "g-" + "24fe7190fcc745e88412c37f95ea6f07"]
        os.environ["ANTHROPIC_API_KEY"] = "my-very-secret-value-123"
        try:
            out = scrub("failed with my-very-secret-value-123 and " + " and ".join(shapes))
        finally:
            del os.environ["ANTHROPIC_API_KEY"]
        self.assertNotIn("my-very-secret-value-123", out)
        for shape in shapes:
            self.assertNotIn(shape.split(" ")[-1], out)

    def test_truncates_and_handles_none(self):
        self.assertEqual(len(scrub("x" * 1000)), 300)
        self.assertEqual(scrub(None), "")


class ParseClaudeOutputTests(unittest.TestCase):
    def test_json_result_gives_text_and_usage(self):
        raw = json.dumps({"type": "result", "result": "hello", "total_cost_usd": 0.5, "num_turns": 3,
                          "usage": {"input_tokens": 7, "output_tokens": 2,
                                    "cache_creation_input_tokens": 1, "cache_read_input_tokens": 4}})
        text, info = parse_claude_output(raw)
        self.assertEqual(text, "hello")
        self.assertEqual(info["cost_usd"], 0.5)
        self.assertEqual(info["input_tokens"], 7)
        self.assertEqual(info["num_turns"], 3)

    def test_plain_text_is_returned_unchanged_with_no_usage(self):
        self.assertEqual(parse_claude_output("VERDICT: SHIP\nok"), ("VERDICT: SHIP\nok", None))

    def test_other_json_is_not_mistaken_for_a_result(self):
        raw = '{"hello": "world"}'
        self.assertEqual(parse_claude_output(raw), (raw, None))
        self.assertEqual(parse_claude_output("[1, 2]"), ("[1, 2]", None))

    def test_missing_or_bad_numbers_become_none_not_zero(self):
        raw = json.dumps({"type": "result", "result": "x", "total_cost_usd": "free", "usage": {"input_tokens": True}})
        text, info = parse_claude_output(raw)
        self.assertEqual(text, "x")
        self.assertIsNone(info["cost_usd"])
        self.assertIsNone(info["input_tokens"])
        self.assertIsNone(info["output_tokens"])

    def test_json_without_result_text_falls_back_to_raw(self):
        raw = json.dumps({"type": "result", "subtype": "error_max_turns"})
        self.assertEqual(parse_claude_output(raw)[0], raw)


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.rec = Recorder(self.tmp, "20260101-000000", "run", "review", "pipeline/20260101-000000")

    def read(self):
        return json.loads(self.rec.path.read_text())

    def test_record_exists_immediately_as_incomplete_and_valid(self):
        d = self.read()
        self.assertEqual(d["status"], "incomplete")
        self.assertIsNone(d["ended_at"])
        self.assertIsNone(d["duration_seconds"])
        assert_valid(self, d)

    def test_stage_timing_and_status(self):
        with self.rec.stage("planner"):
            pass
        stage = self.read()["stages"][0]
        self.assertEqual((stage["name"], stage["status"], stage["attempt"]), ("planner", "ok", 1))
        self.assertGreaterEqual(stage["duration_seconds"], 0)
        self.assertIsNotNone(stage["ended_at"])

    def test_stage_error_is_recorded_scrubbed_and_reraised(self):
        with self.assertRaises(RuntimeError):
            with self.rec.stage("tester", 2):
                raise RuntimeError("bad token " + "co" + "g_SECRETSECRET1")
        stage = self.read()["stages"][0]
        self.assertEqual(stage["status"], "error")
        self.assertNotIn("SECRETSECRET1", json.dumps(self.read()))
        self.assertEqual(stage["attempt"], 2)

    def test_system_exit_inside_a_stage_is_marked_stopped(self):
        with self.assertRaises(SystemExit):
            with self.rec.stage("developer"):
                raise SystemExit(0)
        self.assertEqual(self.read()["stages"][0]["status"], "stopped")

    def test_usage_totals_sum_only_reported_values(self):
        self.rec.usage("planner", "m", {"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": 0,
                                          "cache_read_input_tokens": 100, "cost_usd": 0.25, "num_turns": 2})
        self.rec.usage("tester", "m", None)  # the CLI reported nothing
        t = self.read()["ai_usage"]["totals"]
        self.assertEqual((t["calls"], t["calls_with_cost"]), (2, 1))
        self.assertEqual(t["cost_usd"], 0.25)
        self.assertFalse(t["cost_complete"])
        self.assertEqual(t["input_tokens"], 10)
        self.assertEqual(self.read()["ai_usage"]["cost_source"], "claude_cli_reported")
        assert_valid(self, self.read())

    def test_no_usage_at_all_leaves_everything_null(self):
        self.rec.usage("planner", "m", None)
        t = self.read()["ai_usage"]["totals"]
        self.assertIsNone(t["cost_usd"])
        self.assertIsNone(t["input_tokens"])
        self.assertIsNone(self.read()["ai_usage"]["cost_source"])

    def test_acus_missing_stays_null_and_known_values_add_up(self):
        self.rec.developer_attempt(None)
        self.assertIsNone(self.read()["devin"]["acus_consumed"])
        self.rec.developer_attempt(1.5)
        self.rec.developer_attempt(2)
        d = self.read()
        self.assertEqual(d["devin"]["acus_consumed"], 3.5)
        self.assertEqual((d["devin"]["sessions"], d["devin"]["sessions_with_acus"]), (3, 2))
        self.assertEqual(d["retries"]["retries"], 2)

    def test_pull_request_number_is_parsed_from_url(self):
        self.rec.pull_request(created=True, url="https://github.com/o/r/pull/42")
        pr = self.read()["pull_request"]
        self.assertEqual((pr["created"], pr["number"]), (True, 42))

    def test_finish_first_call_wins_unless_forced(self):
        self.rec.finish("success", "completed")
        self.rec.finish("failure", "exception")
        self.assertEqual(self.read()["status"], "success")
        self.rec.finish("failure", "exception", error=ValueError("x"), force=True)
        d = self.read()
        self.assertEqual((d["status"], d["error"]["type"]), ("failure", "ValueError"))
        self.assertIsNotNone(d["duration_seconds"])
        assert_valid(self, d)

    def test_disabled_recorder_writes_nothing(self):
        tmp = Path(tempfile.mkdtemp())
        Recorder(tmp, "x", "run", "review", "b", enabled=False).finish("success", "completed")
        self.assertFalse((tmp / "metrics").exists())

    def test_fix_records_use_their_own_file_name(self):
        rec = Recorder(self.tmp, "20260101-000000", "fix", "review", "b")
        self.assertTrue(rec.path.name.endswith("-fix.json"))


class SchemaTests(unittest.TestCase):
    def base(self):
        return Recorder(Path(tempfile.mkdtemp()), "r1", "run", "plan", "b").data

    def test_rejects_unknown_status_missing_and_extra_fields(self):
        d = self.base()
        d["status"] = "great"
        self.assertTrue(summarize.validate(d, SCHEMA))
        d = self.base()
        del d["tests"]
        self.assertTrue(any("tests" in p for p in summarize.validate(d, SCHEMA)))
        d = self.base()
        d["prompt"] = "secret idea text"
        self.assertTrue(any("unexpected field 'prompt'" in p for p in summarize.validate(d, SCHEMA)))

    def test_rejects_negative_numbers_and_wrong_types(self):
        d = self.base()
        d["devin"]["acus_consumed"] = -1
        self.assertTrue(summarize.validate(d, SCHEMA))
        d = self.base()
        d["ai_usage"]["totals"]["cost_usd"] = "0.1"
        self.assertTrue(summarize.validate(d, SCHEMA))


if __name__ == "__main__":
    unittest.main()
