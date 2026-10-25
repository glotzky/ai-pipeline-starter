#!/usr/bin/env python3
"""Pipeline orchestrator: researcher -> planner -> [designer] -> Devin -> tester -> reviewer.

Handoffs are files in .pipeline/ committed to a per-run branch. Claude stages run via the
Claude Code CLI (`claude -p`); the developer stage is Devin, driven through its v3 API.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import requests

from run_metrics import Recorder, parse_claude_output, scrub

ROOT = Path(__file__).resolve().parent.parent
PIPE = ROOT / ".pipeline"
AGENTS = ROOT / ".claude" / "agents"
BASE_BRANCH = os.environ.get("BASE_BRANCH", "main")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
REC = None  # metrics Recorder, created in main(); None-safe everywhere it is used
STAGES = ["research", "plan", "design", "dev", "test", "review"]


def sh(*cmd, check=True):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


SRC_EXT = (".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rb", ".java", ".kt", ".rs", ".cs", ".php", ".swift")


def is_test_file(path):
    low = path.lower()
    name = os.path.basename(low)
    return bool(re.search(r"(^|/)(tests?|__tests__|spec)/", low)
                or re.search(r"[._](test|spec)\.[a-z]+$", name) or name.startswith("test_"))


def missing_tests():
    """Return a failure note if the branch changes source code but adds or changes no test file."""
    if os.environ.get("PIPELINE_REQUIRE_TESTS", "1") == "0":
        return ""
    names = sh("git", "diff", "--name-only", f"origin/{BASE_BRANCH}...HEAD").splitlines()
    names = [n for n in names if not n.startswith(".pipeline/")]
    src = [n for n in names if n.endswith(SRC_EXT) and not is_test_file(n)
           and not n.endswith(".d.ts") and ".config." not in os.path.basename(n)]
    if src and not any(is_test_file(n) for n in names):
        return ("No unit tests were added or changed for these source files: "
                + ", ".join(src[:10]) + ". Every new or changed behavior needs unit tests.")
    return ""


def read(name):
    p = PIPE / name
    return p.read_text() if p.exists() else ""


def commit_and_push(branch, message):
    sh("git", "add", "-A")
    if sh("git", "status", "--porcelain"):
        sh("git", "commit", "-m", message)
    sh("git", "push", "-u", "origin", branch)


def load_agent(name):
    text = (AGENTS / f"{name}.md").read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    meta = dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)
    return {k.strip(): v.strip() for k, v in meta.items()}, m.group(2).strip()


def claude_stage(name, task, max_turns=40, attempt=1):
    meta, body = load_agent(name)
    print(f"\n=== {name} ({meta['model']}) ===", flush=True)
    with REC.stage(name, attempt) if REC else nullcontext():
        r = subprocess.run(
            ["claude", "-p", task, "--model", meta["model"], "--append-system-prompt", body,
             "--permission-mode", "acceptEdits", "--max-turns", str(max_turns),
             "--output-format", "json",
             "--allowedTools", ",".join(t.strip() for t in meta["tools"].split(","))],
            cwd=ROOT, capture_output=True, text=True)
        # JSON output carries token counts and cost. If it is not the expected JSON, the raw text is
        # used exactly as before and no usage is recorded.
        text, usage = parse_claude_output(r.stdout)
        if REC:
            REC.usage(name, meta["model"], usage)
        (PIPE / "logs").mkdir(parents=True, exist_ok=True)
        (PIPE / "logs" / f"{name}.txt").write_text(text + "\n---STDERR---\n" + r.stderr)
        if r.returncode != 0:
            raise RuntimeError(f"{name} failed (exit {r.returncode}):\n{r.stderr[-2000:]}")
        return text.strip()


def install_deps():
    """Install project dependencies on the branch AFTER the developer stage.

    The app (or new dependencies) may not have existed when the job started, so this
    must run before the tester. Override with the PIPELINE_INSTALL_CMD repository variable.
    """
    (PIPE / "logs").mkdir(parents=True, exist_ok=True)
    custom = os.environ.get("PIPELINE_INSTALL_CMD", "").strip()
    cmds = []
    if custom:
        cmds = [custom]
    else:
        if (ROOT / "package.json").exists():
            if (ROOT / "pnpm-lock.yaml").exists():
                cmds.append("corepack enable && (pnpm install --frozen-lockfile || pnpm install)")
            elif (ROOT / "yarn.lock").exists():
                cmds.append("corepack enable && (yarn install --frozen-lockfile || yarn install)")
            elif (ROOT / "package-lock.json").exists():
                cmds.append("npm ci || npm install")
            else:
                cmds.append("npm install")
        if (ROOT / "requirements.txt").exists():
            cmds.append("pip install -r requirements.txt")
        elif (ROOT / "pyproject.toml").exists():
            cmds.append("pip install -e . || pip install .")
    if not cmds:
        print("No dependency manifest found; skipping install.", flush=True)
        return
    log = []
    for c in cmds:
        print(f"Installing dependencies: {c}", flush=True)
        r = subprocess.run(c, shell=True, cwd=ROOT, capture_output=True, text=True)
        log.append(f"$ {c}\n{r.stdout}\n{r.stderr}")
        if r.returncode != 0:
            print(f"  install command failed (exit {r.returncode}); see .pipeline/logs/install.txt", flush=True)
    (PIPE / "logs" / "install.txt").write_text("\n".join(log))


# ---------- Devin ----------
DEVIN = "https://api.devin.ai/v3"
ORG = os.environ.get("DEVIN_ORG_ID", "")
DH = {"Authorization": f"Bearer {os.environ.get('DEVIN_API_KEY', '')}"}


def devin_prompt(branch, feedback):
    p = f"""You are the Developer stage of an automated pipeline. Work unattended and do not ask questions.

Repository: {REPO}
Branch: {branch}  (already exists; check it out and commit directly to it)

1. Read CLAUDE.md first (project rules, stack, guardrails). Then read .pipeline/spec.md (and .pipeline/design.md if present). Implement exactly what the spec says.
   Follow the patterns it names. Do not add features it did not ask for. Do not refactor unrelated code.
2. Do NOT open a pull request and do NOT touch the main branch. Push your commits to {branch}.
3. Do not edit .pipeline/spec.md or .pipeline/design.md. Do not weaken or delete existing tests.
   WRITE UNIT TESTS for every new or changed behavior, in the project's existing test framework and location (the spec's "Tests to add" section names them). Cover the happy path, the edge cases the spec names, and at least one failure case. A change with no tests will be rejected.
4. Before finishing, install dependencies and run the project's build/type-check/lint and tests (see CLAUDE.md and the project's manifest), and fix any failures you caused.
5. When done, write .pipeline/changes.md (files changed, what each change does, what the Tester should
   focus on, and a BLOCKERS section if anything prevented you from finishing), commit and push it.
   If you are blocked, record the blocker in changes.md and finish rather than waiting for a reply."""
    if feedback:
        p += f"\n\nThis is a REWORK pass. Fix the problems below, then update changes.md:\n\n{feedback}"
    return p


def devin_run(prompt, timeout_min):
    r = requests.post(f"{DEVIN}/organizations/{ORG}/sessions",
                      headers={**DH, "Content-Type": "application/json"}, json={"prompt": prompt})
    r.raise_for_status()
    s = r.json()
    url = s.get("url")
    print(f"Devin session: {url}", flush=True)
    deadline = time.time() + timeout_min * 60
    idle_polls = 0
    while time.time() < deadline:
        time.sleep(30)
        g = requests.get(f"{DEVIN}/organizations/{ORG}/sessions/{s['session_id']}", headers=DH)
        g.raise_for_status()
        data = g.json()
        status, detail, acus = data.get("status"), data.get("status_detail"), data.get("acus_consumed")
        print(f"  Devin: {status} / {detail} | ACUs: {acus}", flush=True)
        if status in ("exit", "error", "suspended"):
            return url, status, acus
        # Devin reports "running / waiting_for_user" when it is idle (finished, or asking a question).
        # Require two consecutive polls so a brief transient state is not mistaken for completion.
        idle_polls = idle_polls + 1 if detail == "waiting_for_user" else 0
        if idle_polls >= 2:
            return url, "waiting_for_user", acus
    raise TimeoutError(f"Devin session {url} exceeded {timeout_min} minutes")


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("idea")
    ap.add_argument("--until", choices=STAGES, default="review", help="stop after this stage")
    ap.add_argument("--max-retries", type=int, default=2)
    ap.add_argument("--devin-timeout", type=int, default=180, help="minutes")
    ap.add_argument("--fix-branch", default="", help="existing pipeline branch: apply the feedback in IDEA to it (no research/plan)")
    a = ap.parse_args()
    fix = bool(a.fix_branch)
    started = time.time()

    title = next((l.strip().lstrip("#").strip() for l in a.idea.splitlines() if l.strip()), a.idea)[:60]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    branch = a.fix_branch or f"pipeline/{run_id}"
    if fix:
        sh("git", "fetch", "origin", branch)
        sh("git", "checkout", branch)
        sh("git", "pull", "--ff-only", "origin", branch)
    else:
        sh("git", "checkout", "-b", branch)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"branch={branch}\n")
    # Start every run with a clean handoff folder: files from an earlier run that was merged into
    # the default branch (spec.md, test-results.md, ...) must not leak into this one.
    if PIPE.exists() and not fix:
        for child in PIPE.iterdir():
            if child.name != ".gitkeep":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    PIPE.mkdir(exist_ok=True)
    (PIPE / ".gitkeep").touch()
    if fix:  # keep the original idea and spec; record the feedback
        with open(PIPE / "fixes.md", "a") as f:
            f.write(f"\n## Fix request {run_id}\n{a.idea}\n")
    else:
        (PIPE / "idea.md").write_text(a.idea + "\n")
    global REC
    REC = Recorder(ROOT, run_id, "fix" if fix else "run", a.until, branch,
                   enabled=os.environ.get("PIPELINE_METRICS", "1") != "0")
    summary = [f"# Pipeline {'fix' if fix else 'run'} {run_id}", f"{'Feedback' if fix else 'Idea'}: {a.idea}", f"Branch: `{branch}`", ""]

    def write_summary():
        out = "\n".join(summary)
        print("\n" + out)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(out)
        # The workflow posts this file to the issue so you can see why a run stopped.
        (Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "pipeline-summary.md").write_text(out)

    def stop(stage, note=None, code=0, reason=None, post=None):
        """End the run. Finishes the metrics record first so the final record is in the pushed commit."""
        if note:
            summary.append(note)
        if stage == "done":
            REC.finish("success", "completed")
        elif code:
            REC.finish("failure", reason or f"stopped_at_{stage}")
        else:
            REC.finish("stopped", reason or f"until_{stage}")
        commit_and_push(branch, f"pipeline: {stage}")
        write_summary()
        if post:
            post()
        sys.exit(code)

    def reached(stage):
        return a.until == stage

    try:
        if not fix:
            claude_stage("researcher", "Do your job for the idea in .pipeline/idea.md.")
            if reached("research"): stop("research")

            claude_stage("planner", "Do your job for the idea in .pipeline/idea.md.")
            spec = read("spec.md")
            if not re.search(r"^STATUS:\s*READY", spec, re.M):
                stop("plan", "**Planner marked the spec BLOCKED.** Read .pipeline/spec.md on the branch.", reason="planner_blocked")
            if reached("plan"): stop("plan", "Stopped after plan.")

            if re.search(r"NEEDS_DESIGN:\s*yes", spec, re.I):
                claude_stage("designer", "Do your job for the spec in .pipeline/spec.md.")
                summary.append("Design brief produced (.pipeline/design.md).")
            if reached("design"): stop("design", "Stopped after design.")
            commit_and_push(branch, "pipeline: spec and design")

        feedback = ("Human feedback on the pull request. Apply it, keep every existing test passing, "
                    "and add tests for any behavior you change:\n" + a.idea) if fix else None
        verdict, result, devin_urls, acu_sum = "UNKNOWN", "UNKNOWN", [], 0.0
        for attempt in range(a.max_retries + 1):
            print(f"\n##### Developer attempt {attempt + 1} #####", flush=True)
            with REC.stage("developer", attempt + 1):
                url, status, acus = devin_run(devin_prompt(branch, feedback), a.devin_timeout)
            REC.developer_attempt(acus)
            devin_urls.append(f"{url} ({acus} ACUs)")
            try:
                acu_sum += float(acus or 0)
            except (TypeError, ValueError):
                pass
            before = sh("git", "rev-parse", "HEAD")
            sh("git", "pull", "--ff-only", "origin", branch)
            if sh("git", "rev-parse", "HEAD") == before:
                stop("dev", f"**Devin finished ({status}) but pushed no commits.** Open the session to see why (often: Devin cannot access the repo). Session: {url}", code=1, reason="devin_no_commits")
            if reached("dev"): stop("dev", f"Stopped after dev. Devin session: {url} ({acus} ACUs)")
            with REC.stage("install", attempt + 1):
                install_deps()

            claude_stage("tester", "Do your job for the changes on this branch.", max_turns=60, attempt=attempt + 1)
            results = read("test-results.md")
            result = "PASS" if re.match(r"\s*RESULT:\s*PASS", results) else "FAIL"
            gap = missing_tests() if result == "PASS" else ""
            if gap:
                result = "FAIL"
                results = f"RESULT: FAIL\n{gap}\n\n(Tester report below)\n{results}"
                (PIPE / "test-results.md").write_text(results)
            REC.tests(result, gate_failed=bool(gap))
            commit_and_push(branch, f"pipeline: tests (attempt {attempt + 1}) {result}")
            if result == "FAIL" and attempt < a.max_retries:
                feedback = "Tests failed:\n" + results
                REC.retry("tests_failed")
                continue
            if reached("test"): stop("test", f"Stopped after test. Result: {result}")

            review = claude_stage(
                "reviewer", f"Review this branch against origin/{BASE_BRANCH}. Base branch: {BASE_BRANCH}.",
                attempt=attempt + 1)
            (PIPE / "review.md").write_text(review + "\n")
            m = re.search(r"VERDICT:\s*(SHIP|NEEDS WORK|BLOCK)", review)
            verdict = m.group(1) if m else "UNKNOWN"
            REC.review(verdict)
            commit_and_push(branch, f"pipeline: review (attempt {attempt + 1}) {verdict}")
            if verdict == "NEEDS WORK" and attempt < a.max_retries:
                feedback = "Reviewer said NEEDS WORK:\n" + review
                REC.retry("needs_work")
                continue
            break

        minutes = (time.time() - started) / 60
        summary += [f"Tests: **{result}**", f"Verdict: **{verdict}**",
                    "Devin sessions: " + ", ".join(devin_urls),
                    f"Metrics: {minutes:.0f} min, {len(devin_urls)} Devin attempt(s), {acu_sum:.1f} ACUs "
                    f"(full record: metrics/runs/{run_id}{"-fix" if fix else ""}.json)"]
        body = "\n".join(summary) + "\n\n---\n\n" + read("review.md")
        (PIPE / "pr-body.md").write_text(body)
        with REC.stage("pull_request"):
            if fix:
                old_title = sh("gh", "pr", "view", branch, "--json", "title", "--jq", ".title")
                clean = re.sub(r"^\[pipeline [A-Z ]+\]\s*", "", old_title)
                sh("gh", "pr", "comment", branch, "--body-file", str(PIPE / "pr-body.md"))
                sh("gh", "pr", "edit", branch, "--title", f"[pipeline {verdict}] {clean}")
                REC.pull_request(updated=True, url=sh("gh", "pr", "view", branch, "--json", "url", "--jq", ".url", check=False))
            else:
                out = sh("gh", "pr", "create", "--draft", "--base", BASE_BRANCH, "--head", branch,
                         "--title", f"[pipeline {verdict}] {title}", "--body-file", str(PIPE / "pr-body.md"))
                REC.pull_request(created=True, url=out.splitlines()[-1] if out else None)
        # Pull requests opened with the Actions token do not trigger CI by themselves; start it on the
        # final commit (after the metrics record is pushed).
        stop("done", post=lambda: sh("gh", "workflow", "run", "ci.yml", "--ref", branch, check=False))
    except SystemExit:
        raise
    except Exception as e:
        # Push whatever exists (including logs) so failures can be diagnosed from the branch.
        summary.append(f"**FAILED:** {scrub(e, 1500)}")
        REC.finish("failure", "exception", error=e, force=True)
        try:
            commit_and_push(branch, "pipeline: failed (logs attached)")
        except Exception as e2:
            print(f"Could not push failure branch: {e2}")
        write_summary()
        raise


if __name__ == "__main__":
    main()
