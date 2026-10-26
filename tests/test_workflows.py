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

    def test_health_check_lists_failure_watch(self):
        self.assertIn("failure-watch.yml", (WF / "health-check.yml").read_text())


if __name__ == "__main__":
    unittest.main()
