"""Static checks on the workflow files (no PyYAML needed)."""
import re
import unittest

from helpers import REPO

WF = REPO / "template" / ".github" / "workflows"


def code(text):
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#")) + "\n"


def triggers(text):
    m = re.search(r"^on:\n((?:[ \t].*\n|\n)*)", text, re.M)
    return m.group(1) if m else ""


class WorkflowTests(unittest.TestCase):
    def test_pull_request_triggered_workflows_never_use_an_environment(self):
        # Environments are restricted to main; a PR ref (refs/pull/N/merge) is refused, which fails the job.
        for p in WF.glob("*.yml"):
            text = code(p.read_text())
            if re.search(r"^\s+pull_request(_target)?:", triggers(text), re.M):
                self.assertNotRegex(text, r"(?m)^\s+environment:", f"{p.name} runs on pull_request but uses an environment")

    def test_failure_watch_exists_and_watches_the_helpers_but_not_itself_or_the_pipeline(self):
        text = code((WF / "failure-watch.yml").read_text())
        self.assertIn("workflow_run", text)
        self.assertNotIn("environment:", text)
        watched = re.search(r'workflows: \[(.*?)\]', text).group(1)
        self.assertIn('"CI"', watched)
        self.assertNotIn("Failure watch", watched)
        self.assertNotIn("AI pipeline", watched)

    def test_failure_watch_does_not_start_a_fix_unless_the_owner_opted_in(self):
        text = (WF / "failure-watch.yml").read_text()
        self.assertIn('"${AUTO:-}" = "true"', text)

    def test_health_check_knows_every_pipeline_module_and_agent(self):
        text = (WF / "health-check.yml").read_text()
        for f in sorted((REPO / "template" / "pipeline").glob("*.py")):
            self.assertIn(f"pipeline/{f.name}", text, f"{f.name} is not checked by the health check")
        for f in sorted((REPO / "template" / ".claude" / "agents").glob("*.md")):
            self.assertIn(f".claude/agents/{f.name}", text, f"{f.name} is not checked by the health check")

    def test_every_repository_variable_the_pipeline_reads_is_passed_to_it(self):
        run_py = "".join(p.read_text() for p in (REPO / "template" / "pipeline").glob("*.py"))
        wf = code((WF / "pipeline.yml").read_text())
        for var in sorted(set(re.findall(r'environ(?:\.get\(|\[)"(PIPELINE_[A-Z_]+|OLLAMA_[A-Z_]+|ISSUE)"', run_py))):
            if var in ("PIPELINE_PE_TIMEOUT", "PIPELINE_DEMO_WAIT", "PIPELINE_DEMO_NO_INSTALL"):
                continue  # tuning knobs for tests and rare cases: not wired on purpose
            self.assertIn(f"{var}:", wf, f"{var} is read by the pipeline but not passed in pipeline.yml")

    def test_health_check_lists_failure_watch(self):
        self.assertIn("failure-watch.yml", (WF / "health-check.yml").read_text())


if __name__ == "__main__":
    unittest.main()
