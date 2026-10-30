"""Specification verification (optional): ask a Specification Verification Engine (SVE) what "done" means,
then check, with evidence, that the branch meets it.

Standard library only. Off unless the repository variable PIPELINE_SVE_URL is set, and then:
  * prepare()  after planning: turn the idea into a specification with numbered acceptance criteria
               (AC-001, ...), written to .pipeline/acceptance.md for the developer.
  * verify()   after the tester: run the project's tests, upload the JUnit file, and have SVE judge every
               criterion from the test results alone. A criterion is Verified only when a passing test
               names it. No linked passing test, no Verified.

Nothing here calls a model directly; SVE does. A failure to reach SVE never crashes the pipeline: it is
reported as "unverified" with the reason. Secrets (the token) are never put in an error message.
"""
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GATES = ("enforce", "report", "off")
GENERATE_TIMEOUT = 600  # seconds: spec and criteria generation make model calls
CALL_TIMEOUT = 60


class SveError(RuntimeError):
    pass


def settings(env=None):
    e = env if env is not None else os.environ
    gate = (e.get("PIPELINE_SVE_GATE") or "enforce").strip().lower()
    return {
        "url": (e.get("PIPELINE_SVE_URL") or "").strip().rstrip("/"),
        "token": (e.get("PIPELINE_SVE_TOKEN") or "").strip(),
        "test_cmd": (e.get("PIPELINE_SVE_TEST_CMD") or "").strip(),
        "junit": (e.get("PIPELINE_SVE_JUNIT") or "").strip() or str(Path(tempfile.gettempdir()) / "sve-junit.xml"),
        "gate": gate if gate in GATES else "enforce",
    }


def enabled(env=None):
    s = settings(env)
    return bool(s["url"]) and s["gate"] != "off"


def urllib_transport(method, url, headers, body, timeout=CALL_TIMEOUT):
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:
        raise SveError(f"cannot reach the SVE API ({type(exc).__name__})") from None


def _call(cfg, method, path, *, json_body=None, raw=None, params=None, transport=None, timeout=CALL_TIMEOUT):
    url = cfg["url"] + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"authorization": f"Bearer {cfg['token']}"} if cfg["token"] else {}
    body = raw
    if json_body is not None:
        body = json.dumps(json_body).encode()
        headers["content-type"] = "application/json"
    if transport is None:
        status, text = urllib_transport(method, url, headers, body, timeout)
    else:
        status, text = transport(method, url, headers, body)
    if status >= 400:
        try:
            detail = json.loads(text).get("detail", text)
        except (ValueError, AttributeError):
            detail = text
        raise SveError(f"SVE returned {status} for {method} {path}: {str(detail)[:300]}")
    return text


def _json(text, what):
    try:
        return json.loads(text)
    except ValueError:
        raise SveError(f"SVE sent an unreadable answer for {what}") from None


def acceptance_markdown(spec):
    """The developer-facing file: every criterion with its id, and how tests must name it."""
    lines = [
        "# Acceptance criteria (checked by the Specification Verification Engine)",
        "",
        f"Specification `{spec['specification_id']}` v{spec['version']}. These criteria, not your own reading of the idea,",
        "decide whether the work is done.",
        "",
        "## How your tests are matched to criteria",
        "- Put the criterion id in the test's name or title, for example `test_AC_003_rejects_empty_name`",
        "  or `it('AC-003 rejects an empty name', ...)`. One test may name several ids.",
        "- A criterion is Verified only when at least one passing test names it. A failing or erroring test that names it fails it.",
        "- Cover negative criteria too. Do not rename or delete a test that names a criterion.",
        "- If a criterion cannot be automated, say so under BLOCKERS in `.pipeline/changes.md`. It will stay unverified.",
        "",
        "## Criteria",
        "",
    ]
    reqs = {r["id"]: r["description"] for r in spec.get("requirements", [])}
    by_req = {}
    for c in spec.get("acceptance_criteria", []):
        by_req.setdefault(c["requirement_id"], []).append(c)
    for rid, items in by_req.items():
        lines.append(f"### {rid}: {reqs.get(rid, '')}")
        for c in items:
            tag = "" if c.get("testability", "automatable") == "automatable" else f" ({c['testability'].replace('_', ' ')})"
            lines.append(f"- **{c['id']}**{tag}: {c['description']}")
            lines.append(f"  - Expected: {c['expected_outcome']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def prepare(idea, project_name, env=None, transport=None):
    """Create a project, task, specification and criteria in SVE. Returns state for later steps."""
    cfg = settings(env)
    pid = _json(_call(cfg, "POST", "/v1/projects", json_body={"name": project_name[:120] or "pipeline"},
                      transport=transport), "project")["id"]
    tid = _json(_call(cfg, "POST", "/v1/tasks", json_body={"project_id": pid, "text": idea},
                      transport=transport), "task")["id"]
    s1 = _json(_call(cfg, "POST", f"/v1/tasks/{tid}/specifications", transport=transport,
                     timeout=GENERATE_TIMEOUT), "specification")["specification"]
    s2 = _json(_call(cfg, "POST", f"/v1/specifications/{s1['specification_id']}/criteria", transport=transport,
                     timeout=GENERATE_TIMEOUT), "criteria")["specification"]
    if not s2.get("acceptance_criteria"):
        raise SveError("SVE produced no acceptance criteria")
    return {"project_id": pid, "task_id": tid, "specification_id": s2["specification_id"],
            "spec_version": s2["version"], "criteria": len(s2["acceptance_criteria"]),
            "markdown": acceptance_markdown(s2)}


def default_test_cmd(root):
    root = Path(root)
    if any((root / f).exists() for f in ("pytest.ini", "tox.ini", "conftest.py")) or (root / "pyproject.toml").exists():
        return "python -m pytest -q --junitxml={junit}"
    return ""


def _run_tests(cmd, root, junit):
    full = cmd.replace("{junit}", junit)
    r = subprocess.run(full, shell=True, cwd=root, capture_output=True, text=True, timeout=1800)
    return r.returncode


def unverified(reason):
    return {"verified": False, "overall": "unverified", "counts": {}, "report": f"Specification verification: **not verified**. {reason}\n",
            "reason": reason, "run_id": None, "linked": 0, "unlinked_tests": []}


def verify(state, env=None, *, commit_sha=None, root=".", transport=None, runner=None):
    """Run the tests, upload the JUnit result, and return SVE's verdict. Never raises for SVE problems."""
    cfg = settings(env)
    cmd = cfg["test_cmd"] or default_test_cmd(root)
    if not cmd:
        return unverified("No test command is configured. Set the repository variable PIPELINE_SVE_TEST_CMD "
                          "(it must write a JUnit XML file to {junit}).")
    junit = cfg["junit"]
    Path(junit).unlink(missing_ok=True)
    try:
        (runner or _run_tests)(cmd, root, junit)  # a failing suite still writes JUnit; its exit code is not the verdict
    except (OSError, subprocess.TimeoutExpired) as exc:
        return unverified(f"The test command could not run ({type(exc).__name__}).")
    if not Path(junit).exists():
        return unverified(f"The test command wrote no JUnit file to {junit}. Make it produce one "
                          "(for example pytest --junitxml={junit}, or a JUnit reporter in your test runner).")
    try:
        sid = state["specification_id"]
        run = _json(_call(cfg, "POST", f"/v1/specifications/{sid}/runs",
                          json_body={"commit_sha": commit_sha} if commit_sha else {}, transport=transport), "run")
        rid = run["id"]
        up = _json(_call(cfg, "POST", f"/v1/runs/{rid}/evidence/junit", raw=Path(junit).read_bytes(),
                         params={"commit_sha": commit_sha} if commit_sha else None, transport=transport), "evidence")
        ev = _json(_call(cfg, "POST", f"/v1/runs/{rid}/evaluate", transport=transport), "evaluation")
        report = _call(cfg, "GET", f"/v1/runs/{rid}/report", params={"format": "markdown"}, transport=transport)
    except SveError as exc:
        return unverified(str(exc))
    return {"verified": ev["overall"] == "verified", "overall": ev["overall"], "counts": ev["counts"],
            "report": report, "reason": "", "run_id": rid, "linked": up.get("linked", 0),
            "unlinked_tests": up.get("unlinked_tests", [])}


def blocks(result, env=None):
    """True when the gate is 'enforce' and the specification is not fully verified."""
    return settings(env)["gate"] == "enforce" and not result["verified"]


def summary_line(result, env=None):
    gate = settings(env)["gate"]
    counts = ", ".join(f"{v} {k}" for k, v in result.get("counts", {}).items() if v) or "no results"
    text = f"Specification: **{result['overall'].upper()}** ({counts}; gate: {gate})"
    if result.get("reason"):
        text += f". {result['reason']}"
    if result.get("unlinked_tests"):
        text += f". {len(result['unlinked_tests'])} test(s) name no criterion and count for nothing"
    return text


def feedback(result):
    """What the developer is told when the gate blocks a run."""
    return ("The branch does not meet the specification. A criterion is Verified only when a passing test names it "
            "(see .pipeline/acceptance.md). Fix the code or add/rename tests so every automatable criterion has a "
            "passing test that names its id. Report:\n\n" + result["report"])
