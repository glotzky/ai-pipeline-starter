"""Optional specification verification: the pipeline asks SVE what "done" means and checks it with evidence."""
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from helpers import TEMPLATE, Sandbox, git

sys.path.insert(0, str(TEMPLATE / "pipeline"))
import sve_lib  # noqa: E402

IDEA = "Add saved searches\nUsers can save and name searches."
TOKEN = "FAKE-sve-token-for-tests-123"
JUNIT_CMD = """printf '<testsuite><testcase classname="t" name="test_AC_001_saves"/></testsuite>' > {junit}"""

SPEC2 = {
    "specification_id": "spec_2", "version": 2, "task_id": "task_1",
    "requirements": [{"id": "REQ-001", "description": "Users can save a search"}],
    "acceptance_criteria": [
        {"id": "AC-001", "requirement_id": "REQ-001", "description": "A saved search is listed",
         "expected_outcome": "It appears in the list", "testability": "automatable"},
        {"id": "AC-002", "requirement_id": "REQ-001", "description": "Looks nice",
         "expected_outcome": "Reviewer is happy", "testability": "manual_only"},
    ],
}


class StubSve:
    """A tiny stand-in for the SVE HTTP API. `overall` is what /evaluate answers."""

    def __init__(self, overall="verified", fail_criteria=False):
        self.overall, self.fail_criteria = overall, fail_criteria
        self.requests, self.uploads = [], []
        stub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, body, ctype="application/json"):
                data = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body)).encode()
                self.send_response(status)
                self.send_header("content-type", ctype)
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _handle(self):
                n = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(n) if n else b""
                stub.requests.append((self.command, self.path, self.headers.get("authorization")))
                path = self.path.split("?")[0]
                if stub.fail_criteria and path == "/v1/projects":
                    return self._send(500, {"detail": "boom"})
                if path == "/v1/projects":
                    return self._send(201, {"id": "proj_1"})
                if path == "/v1/tasks":
                    return self._send(201, {"id": "task_1"})
                if path == "/v1/tasks/task_1/specifications":
                    return self._send(201, {"specification": {**SPEC2, "specification_id": "spec_1", "version": 1,
                                                              "acceptance_criteria": []}})
                if path == "/v1/specifications/spec_1/criteria":
                    return self._send(201, {"specification": SPEC2})
                if path == "/v1/specifications/spec_2/runs":
                    return self._send(201, {"id": "run_1"})
                if path == "/v1/runs/run_1/evidence/junit":
                    stub.uploads.append(body.decode())
                    return self._send(201, {"ingested": 1, "duplicates_skipped": 0, "linked": 1, "unlinked_tests": []})
                if path == "/v1/runs/run_1/evaluate":
                    counts = {"verified": 1 if stub.overall == "verified" else 0,
                              "failed": 1 if stub.overall == "failed" else 0, "unverified": 0 if stub.overall == "verified" else 1,
                              "blocked": 0}
                    return self._send(200, {"overall": stub.overall, "counts": counts})
                if path == "/v1/runs/run_1/report":
                    return self._send(200, f"# Verification report\nOverall: {stub.overall.upper()}\n", "text/markdown")
                return self._send(404, {"detail": "Not Found"})

            do_GET = do_POST = _handle

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class SveLibUnitTests(unittest.TestCase):
    def test_off_unless_a_url_is_set_and_the_gate_is_not_off(self):
        self.assertFalse(sve_lib.enabled({}))
        self.assertTrue(sve_lib.enabled({"PIPELINE_SVE_URL": "http://x"}))
        self.assertFalse(sve_lib.enabled({"PIPELINE_SVE_URL": "http://x", "PIPELINE_SVE_GATE": "off"}))

    def test_settings_defaults_and_bad_gate_falls_back_to_enforce(self):
        s = sve_lib.settings({"PIPELINE_SVE_URL": "http://x/", "PIPELINE_SVE_GATE": "banana"})
        self.assertEqual((s["url"], s["gate"]), ("http://x", "enforce"))
        self.assertEqual(sve_lib.settings({"PIPELINE_SVE_GATE": "Report"})["gate"], "report")

    def test_acceptance_markdown_lists_ids_and_naming_rule(self):
        md = sve_lib.acceptance_markdown(SPEC2)
        self.assertIn("**AC-001**", md)
        self.assertIn("**AC-002** (manual only)", md)
        self.assertIn("names it", md)
        self.assertIn("### REQ-001: Users can save a search", md)

    def test_verify_without_a_test_command_is_unverified_not_an_error(self):
        r = sve_lib.verify({"specification_id": "spec_2"}, {"PIPELINE_SVE_URL": "http://x"}, root="/nonexistent")
        self.assertFalse(r["verified"])
        self.assertIn("PIPELINE_SVE_TEST_CMD", r["reason"])

    def test_verify_with_a_command_that_writes_no_junit_is_unverified(self):
        env = {"PIPELINE_SVE_URL": "http://x", "PIPELINE_SVE_TEST_CMD": "true", "PIPELINE_SVE_JUNIT": "/tmp/sve-none-xyz.xml"}
        r = sve_lib.verify({"specification_id": "spec_2"}, env, runner=lambda *a: 0)
        self.assertFalse(r["verified"])
        self.assertIn("wrote no JUnit", r["reason"])

    def test_unreachable_sve_is_reported_without_the_token(self):
        env = {"PIPELINE_SVE_URL": "http://127.0.0.1:9", "PIPELINE_SVE_TOKEN": TOKEN}
        with self.assertRaises(sve_lib.SveError) as cm:
            sve_lib.prepare("idea", "p", env)
        self.assertNotIn(TOKEN, str(cm.exception))

    def test_blocks_only_when_enforcing_and_not_verified(self):
        bad, good = sve_lib.unverified("x"), {"verified": True}
        self.assertTrue(sve_lib.blocks(bad, {}))
        self.assertFalse(sve_lib.blocks(bad, {"PIPELINE_SVE_GATE": "report"}))
        self.assertFalse(sve_lib.blocks(good, {}))

    def test_summary_line_mentions_unlinked_tests(self):
        line = sve_lib.summary_line({"overall": "unverified", "counts": {"unverified": 2, "verified": 0},
                                     "unlinked_tests": ["a", "b"], "reason": ""})
        self.assertIn("UNVERIFIED", line)
        self.assertIn("2 test(s) name no criterion", line)


class PipelineSveTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.stub = None

    def start(self, **kw):
        self.stub = StubSve(**kw)
        self.addCleanup(self.stub.close)
        return self.stub

    def env(self, **extra):
        e = {"PIPELINE_SVE_URL": self.stub.url if self.stub else "http://127.0.0.1:9",
             "PIPELINE_SVE_TOKEN": TOKEN, "PIPELINE_SVE_TEST_CMD": JUNIT_CMD,
             "PIPELINE_SVE_JUNIT": str(self.sb.tmp / "junit.xml")}
        e.update(extra)
        return e

    def branch_file(self, path):
        rec = self.sb.record()
        return git("show", f"origin/{rec['branch']}:{path}", cwd=self.sb.project)

    def pr_title(self):
        return [c for c in self.sb.gh_calls() if c.startswith("gh pr create")][0]

    def test_verified_run_passes_through_with_criteria_and_report_in_the_pr(self):
        stub = self.start(overall="verified")
        devin = self.sb.devin()
        code, err = self.sb.run(IDEA, env=self.env(), devin=devin)
        self.assertEqual((code, err), (0, None))
        self.assertIn("**AC-001**", self.branch_file(".pipeline/acceptance.md"))
        self.assertEqual(json.loads(self.branch_file(".pipeline/sve.json"))["specification_id"], "spec_2")
        self.assertIn("ACCEPTANCE CRITERIA", devin.calls[0])
        self.assertIn("[pipeline SHIP]", self.pr_title())
        body = self.branch_file(".pipeline/pr-body.md")
        self.assertIn("## Specification verification", body)
        self.assertIn("Specification: **VERIFIED**", body)
        self.assertIn("test_AC_001_saves", stub.uploads[0])
        self.assertTrue(all(auth == f"Bearer {TOKEN}" for _, _, auth in stub.requests))
        self.assertNotIn(TOKEN, body)

    def test_unverified_run_is_sent_back_to_the_developer_then_lowered_to_needs_work(self):
        self.start(overall="unverified")
        devin = self.sb.devin()
        code, _ = self.sb.run(IDEA, "--max-retries", "1", env=self.env(), devin=devin)
        self.assertEqual(code, 0)
        self.assertEqual(len(devin.calls), 2)
        self.assertIn("does not meet the specification", devin.calls[1])
        self.assertIn("[pipeline NEEDS WORK]", self.pr_title())
        body = self.branch_file(".pipeline/pr-body.md")
        self.assertIn("Verdict lowered from SHIP to NEEDS WORK", body)
        self.assertTrue(self.sb.record()["tests"]["gate_failed"])

    def test_report_gate_informs_but_never_blocks(self):
        self.start(overall="unverified")
        devin = self.sb.devin()
        code, _ = self.sb.run(IDEA, env=self.env(PIPELINE_SVE_GATE="report"), devin=devin)
        self.assertEqual(code, 0)
        self.assertEqual(len(devin.calls), 1)
        self.assertIn("[pipeline SHIP]", self.pr_title())
        self.assertIn("Specification: **UNVERIFIED**", self.branch_file(".pipeline/pr-body.md"))

    def test_sve_down_does_not_crash_the_run_but_nothing_is_called_verified(self):
        devin = self.sb.devin()
        code, err = self.sb.run(IDEA, env=self.env(), devin=devin)
        self.assertEqual((code, err), (0, None))
        self.assertEqual(len(devin.calls), 1)  # retrying cannot fix an unreachable service
        self.assertNotIn("ACCEPTANCE CRITERIA", devin.calls[0])
        self.assertIn("[pipeline NEEDS WORK]", self.pr_title())
        body = self.branch_file(".pipeline/pr-body.md")
        self.assertIn("Specification verification unavailable", body)
        self.assertNotIn(TOKEN, body)

    def test_sve_error_response_is_reported_as_unavailable(self):
        self.start(fail_criteria=True)
        code, err = self.sb.run(IDEA, env=self.env(), devin=self.sb.devin())
        self.assertEqual((code, err), (0, None))
        self.assertIn("Specification verification unavailable", self.branch_file(".pipeline/pr-body.md"))

    def test_nothing_changes_when_sve_is_not_configured(self):
        devin = self.sb.devin()
        code, _ = self.sb.run(IDEA, devin=devin)
        self.assertEqual(code, 0)
        self.assertNotIn("ACCEPTANCE CRITERIA", devin.calls[0])
        self.assertFalse((self.sb.project / ".pipeline" / "acceptance.md").exists())
        self.assertNotIn("Specification", self.branch_file(".pipeline/pr-body.md"))
        self.assertIn("[pipeline SHIP]", self.pr_title())

    def test_failed_tests_skip_verification_and_say_so(self):
        stub = self.start(overall="verified")
        devin = self.sb.devin()
        code, _ = self.sb.run(IDEA, "--max-retries", "0", env=self.env(FAKE_TEST_FAILS="1"), devin=devin)
        self.assertEqual(code, 0)
        self.assertEqual(stub.uploads, [])
        self.assertIn("did not run", self.branch_file(".pipeline/pr-body.md"))


if __name__ == "__main__":
    unittest.main()
