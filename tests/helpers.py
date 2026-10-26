"""Shared test helpers. Standard library only (plus `requests`, which run.py imports; stubbed if missing)."""
import sys

sys.dont_write_bytecode = True  # never leave __pycache__ inside template/ (the installer copies that folder)

import contextlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "template"
sys.path.insert(0, str(TEMPLATE / "metrics"))
import summarize  # noqa: E402

SCHEMA = json.loads((TEMPLATE / "metrics" / "schema.json").read_text())

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
sysprompt = args[args.index("--append-system-prompt") + 1]
mode = os.environ.get("FAKE_CLAUDE_MODE", "json")   # json | json_nocost | text | fail
if mode == "fail":
    sys.stderr.write("boom " + os.environ.get("LEAK_ME", ""))
    sys.exit(1)
pipe = ".pipeline"
os.makedirs(pipe, exist_ok=True)
text = "done"
if "planning specialist" in sysprompt:
    head = "STATUS: BLOCKED" if os.environ.get("FAKE_PLAN") == "blocked" else "STATUS: READY"
    open(pipe + "/spec.md", "w").write(head + "\nNEEDS_DESIGN: no\n# spec\n")
elif "test specialist" in sysprompt:
    counter = os.environ["FAKE_COUNTER"]
    n = int(open(counter).read()) if os.path.exists(counter) else 0
    open(counter, "w").write(str(n + 1))
    fails = int(os.environ.get("FAKE_TEST_FAILS", "0"))
    open(pipe + "/test-results.md", "w").write("RESULT: FAIL\nbroken\n" if n < fails else "RESULT: PASS\nok\n")
elif "senior reviewer" in sysprompt:
    text = os.environ.get("FAKE_VERDICT", "VERDICT: SHIP") + "\nreview text"
elif "research specialist" in sysprompt:
    open(pipe + "/research.md", "w").write("research")
if mode == "text":
    print(text)
    sys.exit(0)
out = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 2, "result": text,
       "usage": {"input_tokens": 10, "output_tokens": 5,
                 "cache_creation_input_tokens": 100, "cache_read_input_tokens": 1000}}
if mode == "json":
    out["total_cost_usd"] = 0.01
print(json.dumps(out))
'''

FAKE_GH = '''#!/bin/bash
echo "gh $*" >> "$GH_LOG"
case "$1 $2" in
  "pr create") echo "https://github.com/o/r/pull/7" ;;
  "pr view") if [[ "$*" == *"--jq .title"* ]]; then echo "[pipeline NEEDS WORK] Add thing"; else echo "https://github.com/o/r/pull/7"; fi ;;
esac
exit 0
'''

SESSION_LINK = "https://app.devin.ai/sessions/SECRET-SESSION-LINK"


def git(*args, cwd, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(r.stderr)
    return r.stdout.strip()


class Sandbox:
    """A scratch project (copy of template/) with a bare 'origin', fake claude and fake gh."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pipeline-test-"))
        self.origin = self.tmp / "origin.git"
        self.project = self.tmp / "project"
        self.bin = self.tmp / "bin"
        self.gh_log = self.tmp / "gh.log"
        self.bin.mkdir()
        for name, body in (("claude", FAKE_CLAUDE), ("gh", FAKE_GH)):
            f = self.bin / name
            f.write_text(body)
            f.chmod(f.stat().st_mode | stat.S_IEXEC)
        subprocess.run(["git", "init", "-q", "--bare", str(self.origin)], check=True)
        shutil.copytree(TEMPLATE, self.project, ignore=shutil.ignore_patterns("__pycache__"))
        (self.project / ".gitignore").write_text("__pycache__/\n")
        git("init", "-q", "-b", "main", cwd=self.project)
        git("config", "user.email", "t@example.com", cwd=self.project)
        git("config", "user.name", "tester", cwd=self.project)
        git("add", "-A", cwd=self.project)
        git("commit", "-qm", "init", cwd=self.project)
        git("remote", "add", "origin", str(self.origin), cwd=self.project)
        git("push", "-q", "origin", "main", cwd=self.project)

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- a fake Devin: pushes a commit from a separate clone, like the real one ----
    def devin(self, tests_from_attempt=1, push=True, acus=2.5, raises=None):
        calls = []

        def devin_run(prompt, timeout):
            calls.append(prompt)
            if raises:
                raise raises
            if not push:
                return SESSION_LINK, "waiting_for_user", acus
            branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=self.project)
            d = Path(tempfile.mkdtemp(dir=self.tmp))
            subprocess.run(["git", "clone", "-q", str(self.origin), str(d)], check=True)
            git("config", "user.email", "d@example.com", cwd=d)
            git("config", "user.name", "devin", cwd=d)
            git("checkout", "-q", branch, cwd=d)
            n = len(calls)
            tag = uuid.uuid4().hex[:8]  # unique names so every fake Devin attempt really changes the repo
            (d / "src").mkdir(exist_ok=True)
            (d / "src" / f"feature{tag}.ts").write_text("export const x = 1;\n")
            if n >= tests_from_attempt:
                (d / "src" / f"feature{tag}.test.ts").write_text("test('x', () => {});\n")
            git("add", "-A", cwd=d)
            git("commit", "-qm", "devin work", cwd=d)
            git("push", "-q", "origin", branch, cwd=d)
            return SESSION_LINK, "waiting_for_user", acus

        devin_run.calls = calls
        return devin_run

    def run(self, *args, env=None, devin=None):
        """Run the project's real run.py main() in-process. Returns (exit_code, exception_or_None)."""
        saved = (dict(os.environ), os.getcwd(), list(sys.path), list(sys.argv))
        try:
            os.environ.clear()
            os.environ.update({
                "PATH": f"{self.bin}{os.pathsep}{saved[0].get('PATH', '')}",
                "HOME": saved[0].get("HOME", str(self.tmp)),
                "GH_LOG": str(self.gh_log), "FAKE_COUNTER": str(self.tmp / "counter"),
                "RUNNER_TEMP": str(self.tmp), "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "1",
                "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
            })
            os.environ.update(env or {})
            os.chdir(self.project)
            sys.path.insert(0, str(self.project / "pipeline"))
            sys.modules.pop("run_metrics", None)
            if "requests" not in sys.modules:
                try:
                    import requests  # noqa: F401
                except ImportError:
                    sys.modules["requests"] = types.ModuleType("requests")
            spec = importlib.util.spec_from_file_location(f"run_{uuid.uuid4().hex}", self.project / "pipeline" / "run.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.devin_run = devin or self.devin()
            mod.install_deps = lambda: None
            sys.argv = ["run.py", *args]
            try:
                with contextlib.redirect_stdout(io.StringIO()):  # keep test output quiet
                    mod.main()
                return 0, None
            except SystemExit as e:
                return (e.code or 0), None
            except BaseException as e:  # noqa: BLE001 (tests inspect any failure)
                return "error", e
        finally:
            os.environ.clear()
            os.environ.update(saved[0])
            os.chdir(saved[1])
            sys.path[:] = saved[2]
            sys.argv[:] = saved[3]
            sys.modules.pop("run_metrics", None)

    # ---- reading results ----
    def records(self):
        return sorted((self.project / "metrics" / "runs").glob("*.json"))

    def record(self, index=0):
        return json.loads(self.records()[index].read_text())

    def branch_record(self, record):
        """The copy of the record that was pushed to the run's branch."""
        suffix = "-fix" if record["kind"] == "fix" else ""
        return json.loads(git("show", f"origin/{record['branch']}:metrics/runs/{record['run_id']}{suffix}.json",
                              cwd=self.project))

    def gh_calls(self):
        return self.gh_log.read_text().splitlines() if self.gh_log.exists() else []


def assert_valid(testcase, record):
    problems = summarize.validate(record, SCHEMA)
    testcase.assertEqual(problems, [], problems)
